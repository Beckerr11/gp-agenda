"""MVP de agendamentos e ordens de serviço da GP Estética Automotiva."""
from __future__ import annotations

import os
import secrets
import sqlite3
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path

from flask import Flask, abort, flash, g, jsonify, redirect, render_template, request, session, url_for, send_from_directory
from werkzeug.security import check_password_hash, generate_password_hash


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS services (
  id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, duration_minutes INTEGER NOT NULL,
  base_price_cents INTEGER NOT NULL, active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS customers (
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, phone TEXT NOT NULL DEFAULT '',
  vehicle TEXT NOT NULL DEFAULT '', notes TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS appointments (
  id INTEGER PRIMARY KEY, customer_id INTEGER NOT NULL REFERENCES customers(id),
  service_id INTEGER NOT NULL REFERENCES services(id), starts_at TEXT NOT NULL,
  ends_at TEXT NOT NULL, quoted_cents INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'agendado' CHECK(status IN
    ('agendado','confirmado','em_execucao','concluido','cancelado')),
  notes TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_appointments_time ON appointments(starts_at, ends_at);
"""
STATUSES = ('agendado', 'confirmado', 'em_execucao', 'concluido', 'cancelado')
ACTIVE_STATUSES = ('agendado', 'confirmado', 'em_execucao')


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get('GP_SECRET_KEY') or secrets.token_hex(32),
        DATABASE=str(Path(app.instance_path) / 'gp_estetica.sqlite3'),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        SESSION_COOKIE_SECURE=os.environ.get('GP_HTTPS') == '1',
        MAX_CONTENT_LENGTH=64 * 1024,
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
    )
    if test_config:
        app.config.update(test_config)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    def db():
        if 'db' not in g:
            g.db = sqlite3.connect(app.config['DATABASE'])
            g.db.row_factory = sqlite3.Row
            g.db.execute('PRAGMA foreign_keys = ON')
        return g.db

    @app.teardown_appcontext
    def close_db(_error=None):
        conn = g.pop('db', None)
        if conn:
            conn.close()

    def init_db():
        db().executescript(SCHEMA)
        db().commit()

    with app.app_context():
        init_db()

    @app.cli.command('create-admin')
    def create_admin():
        """Cria o primeiro usuário a partir de GP_ADMIN_USER e GP_ADMIN_PASSWORD."""
        username = os.environ.get('GP_ADMIN_USER', '').strip()
        password = os.environ.get('GP_ADMIN_PASSWORD', '')
        if not username or len(password) < 12:
            raise SystemExit('Defina GP_ADMIN_USER e GP_ADMIN_PASSWORD (mínimo 12 caracteres).')
        try:
            db().execute('INSERT INTO users(username,password_hash) VALUES (?,?)',
                         (username, generate_password_hash(password, method='scrypt')))
            db().commit()
        except sqlite3.IntegrityError:
            raise SystemExit('Esse usuário já existe.') from None
        print('Administrador criado.')

    def login_required(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            if not session.get('user_id'):
                return redirect(url_for('login'))
            return fn(*args, **kwargs)
        return wrapped

    @app.before_request
    def csrf_guard():
        if request.method == 'POST':
            expected = session.get('csrf_token')
            supplied = request.headers.get('X-CSRF-Token') or request.form.get('csrf_token', '')
            if not expected or not secrets.compare_digest(expected, supplied):
                abort(400, 'Formulário expirado. Recarregue a página.')

    @app.context_processor
    def shared_context():
        if 'csrf_token' not in session:
            session['csrf_token'] = secrets.token_urlsafe(32)
        return {'csrf_token': session['csrf_token'], 'statuses': STATUSES}

    @app.after_request
    def security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['Content-Security-Policy'] = "default-src 'self'; style-src 'self'; script-src 'self'; form-action 'self'; base-uri 'none'"
        response.headers['Cache-Control'] = 'no-store'
        return response

    @app.get('/health')
    def health():
        db().execute('SELECT 1').fetchone()
        return {'status': 'ok'}

    @app.get('/studio')
    def studio():
        return send_from_directory(Path(app.static_folder) / 'react', 'index.html')

    @app.get('/api/session')
    def api_session():
        if 'csrf_token' not in session:
            session['csrf_token'] = secrets.token_urlsafe(32)
        return {'authenticated': bool(session.get('user_id')), 'csrf_token': session['csrf_token']}

    @app.post('/api/login')
    def api_login():
        payload = request.get_json(silent=True) or {}
        user = db().execute('SELECT * FROM users WHERE username=?',
                            (str(payload.get('username', '')).strip(),)).fetchone()
        if not user or not check_password_hash(user['password_hash'], str(payload.get('password', ''))):
            return {'error': 'Usuário ou senha inválidos.'}, 401
        session.clear()
        session['user_id'] = user['id']
        session['csrf_token'] = secrets.token_urlsafe(32)
        session.permanent = True
        return {'authenticated': True, 'csrf_token': session['csrf_token']}

    @app.post('/api/logout')
    def api_logout():
        session.clear()
        return {'ok': True}

    def api_auth():
        if not session.get('user_id'):
            return {'error': 'Entre para continuar.'}, 401
        return None

    @app.get('/api/data')
    def api_data():
        if (failure := api_auth()):
            return failure
        customers_data = [dict(row) for row in db().execute('SELECT * FROM customers ORDER BY name')]
        services_data = [dict(row) for row in db().execute('SELECT * FROM services WHERE active=1 ORDER BY name')]
        appointments_data = [dict(row) for row in db().execute('''SELECT a.*, c.name AS customer,
            c.phone, c.vehicle, s.name AS service FROM appointments a
            JOIN customers c ON c.id=a.customer_id JOIN services s ON s.id=a.service_id
            ORDER BY a.starts_at DESC LIMIT 200''')]
        return {'customers': customers_data, 'services': services_data, 'appointments': appointments_data}

    @app.get('/appointments/<int:appointment_id>/quote')
    @login_required
    def printable_quote(appointment_id):
        quote = db().execute('''SELECT a.*, c.name AS customer, c.phone, c.vehicle,
            s.name AS service, s.duration_minutes FROM appointments a
            JOIN customers c ON c.id=a.customer_id JOIN services s ON s.id=a.service_id
            WHERE a.id=?''', (appointment_id,)).fetchone()
        if quote is None:
            abort(404)
        start = datetime.fromisoformat(quote['starts_at'])
        return render_template('quote.html', quote=quote,
                               scheduled_for=start.strftime('%d/%m/%Y às %H:%M'),
                               status_label={'agendado':'Agendado', 'confirmado':'Confirmado',
                                             'em_execucao':'Em execução', 'concluido':'Concluído',
                                             'cancelado':'Cancelado'}[quote['status']])

    @app.post('/api/customers')
    def api_add_customer():
        if (failure := api_auth()):
            return failure
        p = request.get_json(silent=True) or {}
        name = str(p.get('name', '')).strip()
        phone = str(p.get('phone', '')).strip()
        vehicle = str(p.get('vehicle', '')).strip()
        if not name or len(name) > 120 or len(phone) > 30 or len(vehicle) > 120:
            return {'error': 'Confira nome, telefone e veículo.'}, 400
        cursor = db().execute('INSERT INTO customers(name,phone,vehicle) VALUES (?,?,?)',
                              (name, phone, vehicle))
        db().commit()
        return {'id': cursor.lastrowid}, 201

    @app.post('/api/services')
    def api_add_service():
        if (failure := api_auth()):
            return failure
        p = request.get_json(silent=True) or {}
        name = str(p.get('name', '')).strip()
        try:
            minutes = int(p.get('duration_minutes', 0))
            cents = parse_money(str(p.get('base_price', '')))
        except ValueError:
            minutes, cents = 0, -1
        if not name or len(name) > 100 or not 15 <= minutes <= 1440 or cents < 0:
            return {'error': 'Informe nome, duração e preço válidos.'}, 400
        try:
            cursor = db().execute('INSERT INTO services(name,duration_minutes,base_price_cents) VALUES (?,?,?)',
                                  (name, minutes, cents))
            db().commit()
        except sqlite3.IntegrityError:
            return {'error': 'Já existe um serviço com esse nome.'}, 409
        return {'id': cursor.lastrowid}, 201

    @app.post('/api/appointments')
    def api_add_appointment():
        if (failure := api_auth()):
            return failure
        p = request.get_json(silent=True) or {}
        try:
            customer_id = int(p.get('customer_id', -1))
            service_id = int(p.get('service_id', -1))
            start = datetime.fromisoformat(str(p.get('starts_at', '')))
            quoted = parse_money(str(p.get('quoted_price', '')))
        except ValueError:
            return {'error': 'Confira cliente, serviço, data e orçamento.'}, 400
        service = db().execute('SELECT * FROM services WHERE id=? AND active=1', (service_id,)).fetchone()
        customer = db().execute('SELECT id FROM customers WHERE id=?', (customer_id,)).fetchone()
        if not service or not customer:
            return {'error': 'Cliente ou serviço não encontrado.'}, 400
        notes = str(p.get('notes', '')).strip()
        if len(notes) > 500:
            return {'error': 'Observações muito longas.'}, 400
        end = start + timedelta(minutes=service['duration_minutes'])
        start_s, end_s = start.isoformat(timespec='minutes'), end.isoformat(timespec='minutes')
        collision = db().execute('''SELECT 1 FROM appointments
            WHERE status IN ('agendado','confirmado','em_execucao')
            AND starts_at < ? AND ends_at > ? LIMIT 1''', (end_s, start_s)).fetchone()
        if collision:
            return {'error': 'Horário ocupado. Escolha outro intervalo.'}, 409
        cursor = db().execute('''INSERT INTO appointments
            (customer_id,service_id,starts_at,ends_at,quoted_cents,notes) VALUES (?,?,?,?,?,?)''',
            (customer_id, service_id, start_s, end_s, quoted, notes))
        db().commit()
        return {'id': cursor.lastrowid}, 201

    @app.post('/api/appointments/<int:appointment_id>/status')
    def api_update_status(appointment_id):
        if (failure := api_auth()):
            return failure
        p = request.get_json(silent=True) or {}
        status = str(p.get('status', ''))
        current = db().execute('SELECT * FROM appointments WHERE id=?', (appointment_id,)).fetchone()
        if not current:
            return {'error': 'Agendamento não encontrado.'}, 404
        if status not in STATUSES:
            return {'error': 'Status inválido.'}, 400
        if status in ACTIVE_STATUSES and current['status'] == 'cancelado':
            collision = db().execute('''SELECT 1 FROM appointments
                WHERE id != ? AND status IN ('agendado','confirmado','em_execucao')
                AND starts_at < ? AND ends_at > ? LIMIT 1''',
                (appointment_id, current['ends_at'], current['starts_at'])).fetchone()
            if collision:
                return {'error': 'Horário ocupado. Não é possível reativar.'}, 409
        db().execute('UPDATE appointments SET status=? WHERE id=?', (status, appointment_id))
        db().commit()
        return {'ok': True}

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '')
            user = db().execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
            if user and check_password_hash(user['password_hash'], password):
                session.clear()
                session['user_id'] = user['id']
                session['csrf_token'] = secrets.token_urlsafe(32)
                session.permanent = True
                return redirect(url_for('dashboard'))
            flash('Usuário ou senha inválidos.', 'error')
        return render_template('login.html')

    @app.post('/logout')
    @login_required
    def logout():
        session.clear()
        return redirect(url_for('login'))

    @app.get('/')
    @login_required
    def dashboard():
        appointments = db().execute('''
            SELECT a.*, c.name AS customer, c.vehicle, s.name AS service
            FROM appointments a JOIN customers c ON c.id=a.customer_id
            JOIN services s ON s.id=a.service_id
            ORDER BY a.starts_at DESC LIMIT 100
        ''').fetchall()
        counts = {row['status']: row['n'] for row in db().execute(
            'SELECT status, count(*) n FROM appointments GROUP BY status')}
        return render_template('dashboard.html', appointments=appointments, counts=counts)

    @app.route('/services', methods=['GET', 'POST'])
    @login_required
    def services():
        if request.method == 'POST':
            name = request.form.get('name', '').strip()
            try:
                minutes = int(request.form.get('duration_minutes', ''))
                cents = parse_money(request.form.get('base_price', ''))
            except ValueError:
                minutes, cents = 0, -1
            if not name or len(name) > 100 or not 15 <= minutes <= 1440 or cents < 0:
                flash('Informe nome, duração de 15 a 1440 min e preço válido.', 'error')
            else:
                try:
                    db().execute('INSERT INTO services(name,duration_minutes,base_price_cents) VALUES (?,?,?)',
                                 (name, minutes, cents))
                    db().commit()
                    flash('Serviço cadastrado.', 'success')
                    return redirect(url_for('services'))
                except sqlite3.IntegrityError:
                    flash('Já existe um serviço com esse nome.', 'error')
        rows = db().execute('SELECT * FROM services ORDER BY name').fetchall()
        return render_template('services.html', services=rows)

    @app.route('/customers', methods=['GET', 'POST'])
    @login_required
    def customers():
        if request.method == 'POST':
            name = request.form.get('name', '').strip()
            phone = request.form.get('phone', '').strip()
            vehicle = request.form.get('vehicle', '').strip()
            notes = request.form.get('notes', '').strip()
            if not name or len(name) > 120 or len(phone) > 30 or len(vehicle) > 120 or len(notes) > 500:
                flash('Confira os dados do cliente e os limites dos campos.', 'error')
            else:
                db().execute('INSERT INTO customers(name,phone,vehicle,notes) VALUES (?,?,?,?)',
                             (name, phone, vehicle, notes))
                db().commit()
                flash('Cliente cadastrado.', 'success')
                return redirect(url_for('customers'))
        rows = db().execute('SELECT * FROM customers ORDER BY name').fetchall()
        return render_template('customers.html', customers=rows)

    @app.route('/appointments/new', methods=['GET', 'POST'])
    @login_required
    def new_appointment():
        if request.method == 'POST':
            try:
                customer_id = int(request.form.get('customer_id', ''))
                service_id = int(request.form.get('service_id', ''))
                start = datetime.fromisoformat(request.form.get('starts_at', ''))
                quoted = parse_money(request.form.get('quoted_price', ''))
            except ValueError:
                customer_id = service_id = quoted = -1
                start = None
            service = db().execute('SELECT * FROM services WHERE id=? AND active=1', (service_id,)).fetchone()
            customer = db().execute('SELECT id FROM customers WHERE id=?', (customer_id,)).fetchone()
            notes = request.form.get('notes', '').strip()
            if not start or not service or not customer or quoted < 0 or len(notes) > 500:
                flash('Preencha cliente, serviço, data, orçamento e observações válidos.', 'error')
            else:
                end = start + timedelta(minutes=service['duration_minutes'])
                start_s, end_s = start.isoformat(timespec='minutes'), end.isoformat(timespec='minutes')
                collision = db().execute('''SELECT 1 FROM appointments
                    WHERE status IN ('agendado','confirmado','em_execucao')
                    AND starts_at < ? AND ends_at > ? LIMIT 1''', (end_s, start_s)).fetchone()
                if collision:
                    flash('Horário ocupado. Escolha outro intervalo.', 'error')
                else:
                    db().execute('''INSERT INTO appointments
                        (customer_id,service_id,starts_at,ends_at,quoted_cents,notes)
                        VALUES (?,?,?,?,?,?)''',
                        (customer_id, service_id, start_s, end_s, quoted, notes))
                    db().commit()
                    flash('Agendamento criado.', 'success')
                    return redirect(url_for('dashboard'))
        return render_template('appointment_form.html',
                               customers=db().execute('SELECT * FROM customers ORDER BY name').fetchall(),
                               services=db().execute('SELECT * FROM services WHERE active=1 ORDER BY name').fetchall())

    @app.post('/appointments/<int:appointment_id>/status')
    @login_required
    def update_status(appointment_id: int):
        status = request.form.get('status', '')
        if status not in STATUSES:
            abort(400)
        current = db().execute('SELECT * FROM appointments WHERE id=?', (appointment_id,)).fetchone()
        if not current:
            abort(404)
        if status in ACTIVE_STATUSES and current['status'] == 'cancelado':
            collision = db().execute('''SELECT 1 FROM appointments
                WHERE id != ? AND status IN ('agendado','confirmado','em_execucao')
                AND starts_at < ? AND ends_at > ? LIMIT 1''',
                (appointment_id, current['ends_at'], current['starts_at'])).fetchone()
            if collision:
                flash('Horário ocupado. O agendamento cancelado não foi reativado.', 'error')
                return redirect(url_for('dashboard'))
        db().execute('UPDATE appointments SET status=? WHERE id=?', (status, appointment_id))
        db().commit()
        flash('Status atualizado.', 'success')
        return redirect(url_for('dashboard'))

    @app.template_filter('brl')
    def brl(cents):
        return f'R$ {cents / 100:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')

    return app


def parse_money(value: str) -> int:
    text = value.strip().replace('.', '').replace(',', '.')
    from decimal import Decimal, InvalidOperation
    try:
        amount = Decimal(text)
    except InvalidOperation:
        raise ValueError('Preço inválido') from None
    if not amount.is_finite() or amount < 0 or amount > 100000 or amount.as_tuple().exponent < -2:
        raise ValueError('Preço inválido')
    return int(amount * 100)


app = create_app()
