import re
import tempfile
import unittest
from pathlib import Path

from werkzeug.security import generate_password_hash

from app import create_app


class GPAgendaTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = create_app({
            'TESTING': True,
            'SECRET_KEY': 'test-only',
            'DATABASE': str(Path(self.temp.name) / 'test.sqlite3'),
        })
        self.client = self.app.test_client()
        with self.app.app_context():
            import sqlite3
            conn = sqlite3.connect(self.app.config['DATABASE'])
            conn.execute('INSERT INTO users(username,password_hash) VALUES (?,?)',
                         ('ronaldo', generate_password_hash('senha-exemplo-123', method='scrypt')))
            conn.commit()
            conn.close()

    def tearDown(self):
        self.temp.cleanup()

    def csrf(self):
        with self.client.session_transaction() as sess:
            return sess['csrf_token']

    def login(self):
        self.client.get('/login')
        return self.client.post('/login', data={
            'csrf_token': self.csrf(), 'username': 'ronaldo',
            'password': 'senha-exemplo-123',
        }, follow_redirects=True)

    def test_login_protects_panel_and_rejects_bad_password(self):
        self.assertEqual(self.client.get('/').status_code, 302)
        self.client.get('/login')
        bad = self.client.post('/login', data={
            'csrf_token': self.csrf(), 'username': 'ronaldo', 'password': 'errada',
        }, follow_redirects=True)
        self.assertIn('Usuário ou senha inválidos'.encode(), bad.data)
        good = self.login()
        self.assertIn('Agenda e serviços'.encode(), good.data)

    def test_schedule_rejects_overlap_and_allows_after_cancel(self):
        self.login()
        token = self.csrf()
        self.client.post('/services', data={
            'csrf_token': token, 'name': 'Lavagem completa',
            'duration_minutes': '90', 'base_price': '150,00',
        })
        self.client.post('/customers', data={
            'csrf_token': token, 'name': 'Cliente exemplo', 'phone': '0000',
            'vehicle': 'Carro exemplo',
        })
        base = {
            'csrf_token': token, 'customer_id': '1', 'service_id': '1',
            'quoted_price': '150,00', 'notes': '',
        }
        first = self.client.post('/appointments/new',
                                 data={**base, 'starts_at': '2026-11-16T10:00'},
                                 follow_redirects=True)
        self.assertIn('Agendamento criado'.encode(), first.data)
        overlap = self.client.post('/appointments/new',
                                   data={**base, 'starts_at': '2026-11-16T10:30'},
                                   follow_redirects=True)
        self.assertIn('Horário ocupado'.encode(), overlap.data)
        with self.app.app_context():
            import sqlite3
            conn = sqlite3.connect(self.app.config['DATABASE'])
            count = conn.execute('SELECT count(*) FROM appointments').fetchone()[0]
            price = conn.execute('SELECT quoted_cents FROM appointments').fetchone()[0]
            conn.close()
        self.assertEqual(count, 1)
        self.assertEqual(price, 15000)
        self.client.post('/appointments/1/status',
                         data={'csrf_token': token, 'status': 'cancelado'})
        after_cancel = self.client.post('/appointments/new',
                                        data={**base, 'starts_at': '2026-11-16T10:30'},
                                        follow_redirects=True)
        self.assertIn('Agendamento criado'.encode(), after_cancel.data)
        reactivate = self.client.post('/appointments/1/status',
                                      data={'csrf_token': token, 'status': 'agendado'},
                                      follow_redirects=True)
        self.assertIn('não foi reativado'.encode(), reactivate.data)

    def test_csrf_and_invalid_money(self):
        self.login()
        self.assertEqual(self.client.post('/services', data={'name': 'Teste'}).status_code, 400)
        bad = self.client.post('/services', data={
            'csrf_token': self.csrf(), 'name': 'Teste',
            'duration_minutes': '30', 'base_price': '-10',
        }, follow_redirects=True)
        self.assertIn('preço válido'.encode(), bad.data)

    def test_react_api_full_flow(self):
        session_data = self.client.get('/api/session').get_json()
        token = session_data['csrf_token']
        denied = self.client.get('/api/data')
        self.assertEqual(denied.status_code, 401)
        self.assertEqual(self.client.get('/appointments/1/quote').status_code, 302)
        login = self.client.post('/api/login', json={
            'username': 'ronaldo', 'password': 'senha-exemplo-123'
        }, headers={'X-CSRF-Token': token})
        self.assertEqual(login.status_code, 200)
        token = login.get_json()['csrf_token']
        headers = {'X-CSRF-Token': token}
        service = self.client.post('/api/services', json={
            'name': 'Polimento', 'duration_minutes': 120, 'base_price': '220,00'
        }, headers=headers)
        self.assertEqual(service.status_code, 201)
        customer = self.client.post('/api/customers', json={
            'name': 'Cliente de teste', 'vehicle': 'Veículo de teste'
        }, headers=headers)
        self.assertEqual(customer.status_code, 201)
        booking = {
            'customer_id': customer.get_json()['id'],
            'service_id': service.get_json()['id'],
            'starts_at': '2026-11-16T10:00',
            'quoted_price': '230,00',
            'notes': ''
        }
        first = self.client.post('/api/appointments', json=booking, headers=headers)
        self.assertEqual(first.status_code, 201)
        conflict = self.client.post('/api/appointments',
                                    json={**booking, 'starts_at': '2026-11-16T11:00'},
                                    headers=headers)
        self.assertEqual(conflict.status_code, 409)
        data = self.client.get('/api/data').get_json()
        self.assertEqual(len(data['appointments']), 1)
        self.assertEqual(data['appointments'][0]['quoted_cents'], 23000)
        quote = self.client.get(f"/appointments/{first.get_json()['id']}/quote")
        self.assertEqual(quote.status_code, 200)
        self.assertIn('GP-0001'.encode(), quote.data)
        self.assertIn('R$ 230,00'.encode(), quote.data)
        status = self.client.post(f"/api/appointments/{first.get_json()['id']}/status",
                                  json={'status': 'concluido'}, headers=headers)
        self.assertEqual(status.status_code, 200)
        self.assertEqual(self.client.get('/api/data').get_json()['appointments'][0]['status'], 'concluido')

    def test_react_can_log_in_again_without_reloading_after_logout(self):
        credentials = {'username': 'ronaldo', 'password': 'senha-exemplo-123'}
        first_token = self.client.get('/api/session').get_json()['csrf_token']
        login = self.client.post('/api/login', json=credentials,
                                 headers={'X-CSRF-Token': first_token})
        signed_in_token = login.get_json()['csrf_token']
        logout = self.client.post('/api/logout', json={},
                                  headers={'X-CSRF-Token': signed_in_token})
        self.assertEqual(logout.status_code, 200)
        anonymous = logout.get_json()
        self.assertFalse(anonymous['authenticated'])
        self.assertNotEqual(anonymous['csrf_token'], signed_in_token)
        self.assertEqual(self.client.get('/api/data').status_code, 401)
        second_login = self.client.post('/api/login', json=credentials,
                                        headers={'X-CSRF-Token': anonymous['csrf_token']})
        self.assertEqual(second_login.status_code, 200)
        self.assertTrue(second_login.get_json()['authenticated'])


if __name__ == '__main__':
    unittest.main()
