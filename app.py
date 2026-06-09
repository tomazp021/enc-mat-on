import os
import sqlite3
import secrets
import hashlib
from datetime import datetime
from functools import wraps
from flask import Flask, request, jsonify, session, send_file, render_template
from flask_cors import CORS

app = Flask(__name__, template_folder='templates')
app.secret_key = secrets.token_hex(32)
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = False
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
CORS(app, supports_credentials=True)

DATABASE = 'banco.db'

# ============================================
# FUNÇÕES DE BANCO DE DADOS
# ============================================
def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        # TABELA CATEGORIAS
        conn.execute('''
            CREATE TABLE IF NOT EXISTS categorias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT UNIQUE NOT NULL,
                descricao TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # TABELA USUÁRIOS
        conn.execute('''
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                graduacao TEXT,
                pelotao TEXT,
                login TEXT UNIQUE NOT NULL,
                senha TEXT NOT NULL,
                nivel TEXT NOT NULL,
                status TEXT DEFAULT 'ativo',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # TABELA ESTOQUE COMPANHIA
        conn.execute('''
            CREATE TABLE IF NOT EXISTS estoque_companhia (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo TEXT UNIQUE NOT NULL,
                material TEXT NOT NULL,
                categoria TEXT NOT NULL,
                quantidade_total INTEGER DEFAULT 0,
                quantidade_disponivel INTEGER DEFAULT 0,
                localizacao TEXT,
                observacao TEXT,
                status TEXT DEFAULT 'ATIVO',
                ultima_alteracao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # TABELA ESTOQUE PELOTÃO
        conn.execute('''
            CREATE TABLE IF NOT EXISTS estoque_pelotao (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pelotao TEXT NOT NULL,
                material_id INTEGER NOT NULL,
                material_nome TEXT NOT NULL,
                quantidade INTEGER DEFAULT 0,
                status TEXT DEFAULT 'DISPONIVEL',
                ultima_movimentacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (material_id) REFERENCES estoque_companhia(id)
            )
        ''')
        
        # TABELA MOVIMENTAÇÕES
        conn.execute('''
            CREATE TABLE IF NOT EXISTS movimentacoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo TEXT NOT NULL,
                material_id INTEGER NOT NULL,
                material_nome TEXT NOT NULL,
                quantidade INTEGER NOT NULL,
                usuario TEXT NOT NULL,
                pelotao TEXT NOT NULL,
                nome_militar TEXT,
                responsavel TEXT,
                data TEXT NOT NULL,
                hora TEXT NOT NULL,
                observacao TEXT,
                ip TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # TABELA BACKUPS
        conn.execute('''
            CREATE TABLE IF NOT EXISTS backups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                arquivo TEXT NOT NULL,
                data TEXT NOT NULL,
                usuario TEXT NOT NULL,
                tamanho TEXT
            )
        ''')
        
        # TABELA LOGS
        conn.execute('''
            CREATE TABLE IF NOT EXISTS logs_auditoria (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario TEXT NOT NULL,
                data TEXT NOT NULL,
                hora TEXT NOT NULL,
                acao TEXT NOT NULL,
                material TEXT,
                quantidade TEXT,
                pelotao TEXT,
                ip TEXT,
                detalhes TEXT
            )
        ''')
        
        # CATEGORIAS PADRÃO
        categorias_padrao = [
            ('Fardamento', 'Uniformes e vestimentas militares'),
            ('Equipamentos', 'Equipamentos táticos e de proteção'),
            ('Material administrativo', 'Materiais de escritório'),
            ('Limpeza', 'Produtos de limpeza'),
            ('Reserva operacional', 'Materiais de reserva'),
            ('Armamento', 'Armas e munições'),
            ('Comunicação', 'Equipamentos de comunicação'),
            ('Acessórios', 'Acessórios diversos')
        ]
        for nome, desc in categorias_padrao:
            conn.execute('INSERT OR IGNORE INTO categorias (nome, descricao) VALUES (?, ?)', (nome, desc))
        
        # USUÁRIOS PADRÃO
        usuarios_padrao = [
            ('Desenvolvedor', 'DEV', 'dev', hashlib.sha256('dev123'.encode()).hexdigest(), 'DEV', 'ativo', None),
            ('Sub Tenente', 'SUB', 'sub', hashlib.sha256('sub123'.encode()).hexdigest(), 'SUB', 'ativo', None),
            ('Cabo Silva', '1º Pelotão', 'pelotao1', hashlib.sha256('123'.encode()).hexdigest(), 'RESP', 'ativo', '1º Pelotão'),
            ('Cabo Santos', '2º Pelotão', 'pelotao2', hashlib.sha256('123'.encode()).hexdigest(), 'RESP', 'ativo', '2º Pelotão'),
            ('Cabo Oliveira', '3º Pelotão', 'pelotao3', hashlib.sha256('123'.encode()).hexdigest(), 'RESP', 'ativo', '3º Pelotão'),
            ('Soldado Leitura', 'LEITURA', 'leitura', hashlib.sha256('leitura123'.encode()).hexdigest(), 'LEITURA', 'ativo', None)
        ]
        for nome, nivel, login, senha, nivel_user, status, pelotao in usuarios_padrao:
            conn.execute('''
                INSERT OR IGNORE INTO usuarios (nome, graduacao, pelotao, login, senha, nivel, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (nome, nome, pelotao, login, senha, nivel_user, status))
        
        # MATERIAIS PADRÃO
        materiais_padrao = [
            ('FARD-001', 'Farda de Combate', 'Fardamento', 50, 50, 'Almoxarifado A1', 'Farda camuflada'),
            ('FARD-002', 'Coturno', 'Fardamento', 100, 100, 'Almoxarifado A1', 'Coturno preto'),
            ('EQP-001', 'Capacete Balístico', 'Equipamentos', 30, 30, 'Arsenal B2', 'Capacete de proteção'),
            ('EQP-002', 'Colete Balístico', 'Equipamentos', 28, 28, 'Arsenal B2', 'Colete à prova de balas'),
            ('ADM-001', 'Computador', 'Material administrativo', 10, 10, 'Sala TI', 'Desktop'),
            ('ADM-002', 'Impressora', 'Material administrativo', 5, 5, 'Sala TI', 'Impressora multifuncional'),
            ('LIM-001', 'Vassoura', 'Limpeza', 20, 20, 'Depósito C3', 'Vassoura de piaçava'),
            ('LIM-002', 'Desinfetante', 'Limpeza', 30, 30, 'Depósito C3', 'Desinfetante 1L'),
            ('RES-001', 'Kit Emergência', 'Reserva operacional', 15, 15, 'Almoxarifado', 'Primeiros socorros'),
            ('RES-002', 'Barraca', 'Reserva operacional', 10, 10, 'Almoxarifado', 'Barraca de campanha')
        ]
        for cod, nome, cat, qtd, qtd_disp, loc, obs in materiais_padrao:
            conn.execute('''
                INSERT OR IGNORE INTO estoque_companhia 
                (codigo, material, categoria, quantidade_total, quantidade_disponivel, localizacao, observacao, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (cod, nome, cat, qtd, qtd_disp, loc, obs, 'ATIVO'))
        
        # ESTOQUE INICIAL DOS PELOTÕES
        materiais = conn.execute('SELECT id, material FROM estoque_companhia').fetchall()
        pelotoes = ['1º Pelotão', '2º Pelotão', '3º Pelotão', 'Material SUB']
        for material in materiais:
            for pelotao in pelotoes:
                existe = conn.execute('''
                    SELECT id FROM estoque_pelotao WHERE pelotao = ? AND material_id = ?
                ''', (pelotao, material['id'])).fetchone()
                if not existe:
                    conn.execute('''
                        INSERT INTO estoque_pelotao (pelotao, material_id, material_nome, quantidade, status)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (pelotao, material['id'], material['material'], 0, 'DISPONIVEL'))
        
        conn.commit()
        print("✅ Banco inicializado com sucesso!")

# ============================================
# DECORADORES
# ============================================
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'success': False, 'message': 'Não autenticado'}), 401
        return f(*args, **kwargs)
    return decorated

def nivel_required(niveis):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if 'user_nivel' not in session:
                return jsonify({'success': False, 'message': 'Não autenticado'}), 401
            if session['user_nivel'] not in niveis:
                return jsonify({'success': False, 'message': 'Acesso negado'}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator

# ============================================
# ROTAS HTML
# ============================================
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/estoque_companhia')
def estoque_companhia():
    return render_template('estoque_companhia.html')

@app.route('/reserva_pelotao')
def reserva_pelotao():
    return render_template('reserva_pelotao.html')

@app.route('/cautela')
def cautela():
    return render_template('cautela.html')

@app.route('/historico')
def historico():
    return render_template('historico.html')

@app.route('/relatorios')
def relatorios():
    return render_template('relatorios.html')

@app.route('/usuarios')
def usuarios():
    return render_template('usuarios.html')

@app.route('/configuracoes')
def configuracoes():
    return render_template('configuracoes.html')

# ============================================
# API AUTENTICAÇÃO
# ============================================
@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json
    login = data.get('login')
    senha = data.get('senha')
    
    if not login or not senha:
        return jsonify({'success': False, 'message': 'Preencha usuário e senha'}), 400
    
    senha_hash = hashlib.sha256(senha.encode()).hexdigest()
    
    with get_db() as conn:
        user = conn.execute('''
            SELECT * FROM usuarios 
            WHERE login = ? AND senha = ? AND status = 'ativo'
        ''', (login, senha_hash)).fetchone()
        
        if user:
            session.clear()
            session['user_id'] = user['id']
            session['user_nome'] = user['nome']
            session['user_login'] = user['login']
            session['user_nivel'] = user['nivel']
            session['user_pelotao'] = user['pelotao']
            
            now = datetime.now()
            conn.execute('''
                INSERT INTO logs_auditoria (usuario, data, hora, acao, ip, detalhes)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user['nome'], now.strftime('%d/%m/%Y'), now.strftime('%H:%M:%S'), 
                  'LOGIN', request.remote_addr, 'Login realizado com sucesso'))
            conn.commit()
            
            return jsonify({
                'success': True,
                'user': {
                    'nome': user['nome'],
                    'nivel': user['nivel'],
                    'pelotao': user['pelotao']
                }
            })
    
    return jsonify({'success': False, 'message': 'Usuário ou senha inválidos'}), 401

@app.route('/api/usuario_atual', methods=['GET'])
@login_required
def usuario_atual():
    return jsonify({
        'id': session['user_id'],
        'nome': session['user_nome'],
        'login': session['user_login'],
        'nivel': session['user_nivel'],
        'pelotao': session.get('user_pelotao')
    })

@app.route('/api/logout', methods=['POST'])
def logout():
    if 'user_nome' in session:
        with get_db() as conn:
            now = datetime.now()
            conn.execute('''
                INSERT INTO logs_auditoria (usuario, data, hora, acao, ip, detalhes)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (session['user_nome'], now.strftime('%d/%m/%Y'), now.strftime('%H:%M:%S'), 
                  'LOGOUT', request.remote_addr, 'Logout realizado'))
            conn.commit()
    session.clear()
    return jsonify({'success': True})

# ============================================
# API DASHBOARD
# ============================================
@app.route('/api/dashboard', methods=['GET'])
@login_required
def api_dashboard():
    with get_db() as conn:
        total_estoque = conn.execute('SELECT SUM(quantidade_total) as total FROM estoque_companhia').fetchone()['total'] or 0
        itens_baixos = conn.execute('SELECT COUNT(*) as count FROM estoque_companhia WHERE quantidade_disponivel < 10').fetchone()['count'] or 0
        total_cautelas = conn.execute("SELECT COUNT(*) as count FROM movimentacoes WHERE tipo = 'CAUTELA'").fetchone()['count'] or 0
        total_descautelas = conn.execute("SELECT COUNT(*) as count FROM movimentacoes WHERE tipo = 'DESCAUTELA'").fetchone()['count'] or 0
        
        resumo_pelotoes = conn.execute('''
            SELECT pelotao, SUM(quantidade) as total 
            FROM estoque_pelotao 
            GROUP BY pelotao 
            ORDER BY pelotao
        ''').fetchall()
        resumo_pelotoes_list = [{'nome': p['pelotao'], 'total': p['total'] or 0} for p in resumo_pelotoes]
        
        movimentacoes = conn.execute('''
            SELECT data, hora, material_nome, tipo, quantidade, usuario, pelotao 
            FROM movimentacoes 
            ORDER BY created_at DESC 
            LIMIT 10
        ''').fetchall()
        movimentacoes_list = [
            {
                'data': m['data'],
                'hora': m['hora'],
                'material_nome': m['material_nome'],
                'tipo': m['tipo'],
                'quantidade': m['quantidade'],
                'usuario': m['usuario'],
                'pelotao': m['pelotao']
            }
            for m in movimentacoes
        ]
        
        return jsonify({
            'success': True,
            'total_estoque': total_estoque,
            'itens_baixos': itens_baixos,
            'total_cautelas': total_cautelas,
            'total_descautelas': total_descautelas,
            'resumo_pelotoes': resumo_pelotoes_list,
            'movimentacoes': movimentacoes_list
        })

# ============================================
# API CATEGORIAS
# ============================================
@app.route('/api/categorias', methods=['GET'])
@login_required
def api_get_categorias():
    with get_db() as conn:
        categorias = conn.execute('SELECT * FROM categorias ORDER BY nome').fetchall()
        return jsonify({'success': True, 'categorias': [dict(c) for c in categorias]})

@app.route('/api/categorias', methods=['POST'])
@login_required
@nivel_required(['DEV'])
def api_create_categoria():
    data = request.json
    nome = data.get('nome', '').strip()
    descricao = data.get('descricao', '').strip()
    
    if not nome:
        return jsonify({'success': False, 'message': 'Nome da categoria é obrigatório'}), 400
    
    with get_db() as conn:
        try:
            conn.execute('INSERT INTO categorias (nome, descricao) VALUES (?, ?)', (nome, descricao))
            conn.commit()
            return jsonify({'success': True, 'message': 'Categoria criada com sucesso'})
        except sqlite3.IntegrityError:
            return jsonify({'success': False, 'message': 'Categoria já existe'}), 400

@app.route('/api/categorias/<int:id>', methods=['PUT'])
@login_required
@nivel_required(['DEV'])
def api_update_categoria(id):
    data = request.json
    nome = data.get('nome', '').strip()
    descricao = data.get('descricao', '').strip()
    
    if not nome:
        return jsonify({'success': False, 'message': 'Nome da categoria é obrigatório'}), 400
    
    with get_db() as conn:
        try:
            conn.execute('UPDATE categorias SET nome = ?, descricao = ? WHERE id = ?', (nome, descricao, id))
            conn.commit()
            return jsonify({'success': True, 'message': 'Categoria atualizada'})
        except sqlite3.IntegrityError:
            return jsonify({'success': False, 'message': 'Categoria já existe'}), 400

@app.route('/api/categorias/<int:id>', methods=['DELETE'])
@login_required
@nivel_required(['DEV'])
def api_delete_categoria(id):
    with get_db() as conn:
        em_uso = conn.execute('''
            SELECT COUNT(*) as count FROM estoque_companhia 
            WHERE categoria = (SELECT nome FROM categorias WHERE id = ?)
        ''', (id,)).fetchone()['count']
        
        if em_uso > 0:
            return jsonify({'success': False, 'message': 'Categoria está sendo usada por materiais'}), 400
        
        conn.execute('DELETE FROM categorias WHERE id = ?', (id,))
        conn.commit()
        return jsonify({'success': True, 'message': 'Categoria removida com sucesso'})

# ============================================
# API ESTOQUE COMPANHIA
# ============================================
@app.route('/api/estoque_companhia', methods=['GET'])
@login_required
def api_get_estoque_companhia():
    with get_db() as conn:
        estoque = conn.execute('SELECT * FROM estoque_companhia ORDER BY categoria, material').fetchall()
        return jsonify({'success': True, 'materiais': [dict(row) for row in estoque]})

@app.route('/api/estoque_companhia', methods=['POST'])
@login_required
@nivel_required(['DEV', 'SUB'])
def api_create_estoque_companhia():
    data = request.json
    
    with get_db() as conn:
        try:
            conn.execute('''
                INSERT INTO estoque_companhia 
                (codigo, material, categoria, quantidade_total, quantidade_disponivel, localizacao, observacao, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (data['codigo'], data['material'], data['categoria'], 
                  data['quantidade_total'], data['quantidade_disponivel'],
                  data.get('localizacao', ''), data.get('observacao', ''), 'ATIVO'))
            conn.commit()
            return jsonify({'success': True, 'message': 'Material cadastrado com sucesso'})
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/estoque_companhia/<int:id>', methods=['PUT'])
@login_required
@nivel_required(['DEV', 'SUB'])
def api_update_estoque_companhia(id):
    data = request.json
    
    with get_db() as conn:
        conn.execute('''
            UPDATE estoque_companhia 
            SET codigo=?, material=?, categoria=?, quantidade_total=?, 
                quantidade_disponivel=?, localizacao=?, observacao=?, 
                ultima_alteracao=CURRENT_TIMESTAMP
            WHERE id=?
        ''', (data.get('codigo'), data.get('material'), data.get('categoria'),
              data.get('quantidade_total'), data.get('quantidade_disponivel'),
              data.get('localizacao'), data.get('observacao'), id))
        conn.commit()
        return jsonify({'success': True, 'message': 'Material atualizado com sucesso'})

@app.route('/api/estoque_companhia/<int:id>', methods=['DELETE'])
@login_required
@nivel_required(['DEV', 'SUB'])
def api_delete_estoque_companhia(id):
    with get_db() as conn:
        em_uso = conn.execute('SELECT COUNT(*) as count FROM movimentacoes WHERE material_id = ?', (id,)).fetchone()['count']
        if em_uso > 0:
            return jsonify({'success': False, 'message': 'Material possui movimentações e não pode ser excluído. Desative-o.'}), 400
        
        conn.execute('DELETE FROM estoque_pelotao WHERE material_id = ?', (id,))
        conn.execute('DELETE FROM estoque_companhia WHERE id = ?', (id,))
        conn.commit()
        return jsonify({'success': True, 'message': 'Material excluído com sucesso'})

@app.route('/api/estoque_companhia/<int:id>/status', methods=['PUT'])
@login_required
@nivel_required(['DEV', 'SUB'])
def api_update_estoque_status(id):
    data = request.json
    with get_db() as conn:
        conn.execute('UPDATE estoque_companhia SET status = ? WHERE id = ?', (data.get('status'), id))
        conn.commit()
        return jsonify({'success': True, 'message': 'Status atualizado com sucesso'})

# ============================================
# API ESTOQUE PELOTÃO
# ============================================
@app.route('/api/estoque_pelotao', methods=['GET'])
@login_required
def api_get_estoque_pelotao():
    with get_db() as conn:
        estoque = conn.execute('''
            SELECT ep.*, ec.codigo, ec.categoria 
            FROM estoque_pelotao ep
            JOIN estoque_companhia ec ON ep.material_id = ec.id
            ORDER BY ep.pelotao, ep.material_nome
        ''').fetchall()
        return jsonify({'success': True, 'estoque': [dict(row) for row in estoque]})

@app.route('/api/estoque_pelotao', methods=['POST'])
@login_required
@nivel_required(['DEV', 'SUB', 'RESP'])
def api_create_estoque_pelotao():
    data = request.json
    
    with get_db() as conn:
        existe = conn.execute('''
            SELECT id FROM estoque_pelotao WHERE pelotao = ? AND material_id = ?
        ''', (data['pelotao'], data['material_id'])).fetchone()
        
        if existe:
            conn.execute('''
                UPDATE estoque_pelotao 
                SET quantidade = quantidade + ?, ultima_movimentacao = CURRENT_TIMESTAMP
                WHERE pelotao = ? AND material_id = ?
            ''', (data['quantidade'], data['pelotao'], data['material_id']))
        else:
            conn.execute('''
                INSERT INTO estoque_pelotao (pelotao, material_id, material_nome, quantidade, status)
                VALUES (?, ?, ?, ?, ?)
            ''', (data['pelotao'], data['material_id'], data['material_nome'], data['quantidade'], 'DISPONIVEL'))
        conn.commit()
        return jsonify({'success': True, 'message': 'Produto adicionado ao pelotão'})

@app.route('/api/estoque_pelotao/<int:id>', methods=['PUT'])
@login_required
def api_update_estoque_pelotao(id):
    data = request.json
    
    with get_db() as conn:
        conn.execute('''
            UPDATE estoque_pelotao 
            SET quantidade = ?, ultima_movimentacao = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (data['quantidade'], id))
        conn.commit()
        return jsonify({'success': True, 'message': 'Quantidade atualizada'})

@app.route('/api/estoque_pelotao/<int:id>/status', methods=['PUT'])
@login_required
def api_update_estoque_pelotao_status(id):
    data = request.json
    
    with get_db() as conn:
        conn.execute('UPDATE estoque_pelotao SET status = ? WHERE id = ?', (data['status'], id))
        conn.commit()
        return jsonify({'success': True, 'message': 'Status atualizado'})

@app.route('/api/estoque_pelotao/<int:id>', methods=['DELETE'])
@login_required
def api_delete_estoque_pelotao(id):
    with get_db() as conn:
        conn.execute('DELETE FROM estoque_pelotao WHERE id = ?', (id,))
        conn.commit()
        return jsonify({'success': True, 'message': 'Item removido do pelotão'})

@app.route('/api/estoque_pelotao/verificar', methods=['GET'])
@login_required
def api_verificar_estoque_pelotao():
    pelotao = request.args.get('pelotao')
    material_id = request.args.get('material_id')
    
    with get_db() as conn:
        item = conn.execute('''
            SELECT quantidade FROM estoque_pelotao 
            WHERE pelotao = ? AND material_id = ?
        ''', (pelotao, material_id)).fetchone()
        disponivel = item['quantidade'] if item else 0
        return jsonify({'quantidade': disponivel})

# ============================================
# API MOVIMENTAÇÕES
# ============================================
@app.route('/api/movimentacoes', methods=['GET'])
@login_required
def api_get_movimentacoes():
    with get_db() as conn:
        movimentacoes = conn.execute('''
            SELECT * FROM movimentacoes ORDER BY created_at DESC LIMIT 500
        ''').fetchall()
        return jsonify({'success': True, 'movimentacoes': [dict(row) for row in movimentacoes]})

@app.route('/api/cautela', methods=['POST'])
@login_required
def api_cautela():
    data = request.json
    tipo = data.get('tipo')
    material_id = data.get('material_id')
    quantidade = data.get('quantidade')
    observacao = data.get('observacao', '')
    pelotao_destino = data.get('pelotao')
    nome_militar = data.get('nome_militar', '')
    responsavel = data.get('responsavel', '')
    
    with get_db() as conn:
        material = conn.execute('SELECT * FROM estoque_companhia WHERE id = ?', (material_id,)).fetchone()
        if not material:
            return jsonify({'success': False, 'message': 'Material não encontrado'}), 404
        
        if tipo == 'CAUTELA':
            if material['quantidade_disponivel'] < quantidade:
                return jsonify({'success': False, 'message': f'Estoque insuficiente. Disponível: {material["quantidade_disponivel"]}'}), 400
            
            nova_qtd = material['quantidade_disponivel'] - quantidade
            conn.execute('UPDATE estoque_companhia SET quantidade_disponivel = ? WHERE id = ?', (nova_qtd, material_id))
            
            estoque_pel = conn.execute('''
                SELECT * FROM estoque_pelotao WHERE pelotao = ? AND material_id = ?
            ''', (pelotao_destino, material_id)).fetchone()
            
            if estoque_pel:
                nova_qtd_pel = estoque_pel['quantidade'] + quantidade
                conn.execute('''
                    UPDATE estoque_pelotao SET quantidade = ?, ultima_movimentacao = CURRENT_TIMESTAMP
                    WHERE pelotao = ? AND material_id = ?
                ''', (nova_qtd_pel, pelotao_destino, material_id))
            else:
                conn.execute('''
                    INSERT INTO estoque_pelotao (pelotao, material_id, material_nome, quantidade, status)
                    VALUES (?, ?, ?, ?, ?)
                ''', (pelotao_destino, material_id, material['material'], quantidade, 'DISPONIVEL'))
            
            detalhes = f'Cautela de {quantidade} unidade(s) para {pelotao_destino}'
        else:
            estoque_pel = conn.execute('''
                SELECT * FROM estoque_pelotao WHERE pelotao = ? AND material_id = ?
            ''', (pelotao_destino, material_id)).fetchone()
            
            if not estoque_pel or estoque_pel['quantidade'] < quantidade:
                return jsonify({'success': False, 'message': 'Quantidade insuficiente no pelotão'}), 400
            
            nova_qtd_pel = estoque_pel['quantidade'] - quantidade
            if nova_qtd_pel == 0:
                conn.execute('DELETE FROM estoque_pelotao WHERE id = ?', (estoque_pel['id'],))
            else:
                conn.execute('''
                    UPDATE estoque_pelotao SET quantidade = ?, ultima_movimentacao = CURRENT_TIMESTAMP
                    WHERE pelotao = ? AND material_id = ?
                ''', (nova_qtd_pel, pelotao_destino, material_id))
            
            nova_qtd = material['quantidade_disponivel'] + quantidade
            conn.execute('UPDATE estoque_companhia SET quantidade_disponivel = ? WHERE id = ?', (nova_qtd, material_id))
            
            detalhes = f'Descautela de {quantidade} unidade(s) do {pelotao_destino}'
        
        now = datetime.now()
        conn.execute('''
            INSERT INTO movimentacoes 
            (tipo, material_id, material_nome, quantidade, usuario, pelotao, nome_militar, responsavel, data, hora, observacao, ip)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (tipo, material_id, material['material'], quantidade, session['user_nome'],
              pelotao_destino, nome_militar, responsavel, now.strftime('%d/%m/%Y'),
              now.strftime('%H:%M:%S'), observacao, request.remote_addr))
        
        conn.execute('''
            INSERT INTO logs_auditoria (usuario, data, hora, acao, material, quantidade, pelotao, ip, detalhes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (session['user_nome'], now.strftime('%d/%m/%Y'), now.strftime('%H:%M:%S'),
              tipo, material['material'], str(quantidade), pelotao_destino, 
              request.remote_addr, detalhes))
        
        conn.commit()
        return jsonify({'success': True, 'message': f'{tipo} registrada com sucesso!'})

# ============================================
# API LOGS
# ============================================
@app.route('/api/logs_auditoria', methods=['GET'])
@login_required
@nivel_required(['DEV', 'SUB'])
def api_get_logs():
    with get_db() as conn:
        logs = conn.execute('SELECT * FROM logs_auditoria ORDER BY id DESC LIMIT 1000').fetchall()
        return jsonify({'success': True, 'logs': [dict(row) for row in logs]})

# ============================================
# API USUÁRIOS
# ============================================
@app.route('/api/usuarios', methods=['GET'])
@login_required
@nivel_required(['DEV', 'SUB'])
def api_get_usuarios():
    with get_db() as conn:
        usuarios = conn.execute('''
            SELECT id, nome, pelotao, login, nivel, status, created_at 
            FROM usuarios ORDER BY id
        ''').fetchall()
        return jsonify({'success': True, 'usuarios': [dict(row) for row in usuarios]})

@app.route('/api/usuarios', methods=['POST'])
@login_required
@nivel_required(['DEV', 'SUB'])
def api_create_usuario():
    data = request.json
    senha_hash = hashlib.sha256(data['senha'].encode()).hexdigest()
    
    login = data.get('login') or data['nome'].lower().replace(' ', '_')
    
    with get_db() as conn:
        try:
            existe = conn.execute('SELECT id FROM usuarios WHERE login = ?', (login,)).fetchone()
            if existe:
                return jsonify({'success': False, 'message': 'Login já existe. Use outro nome.'}), 400
            
            conn.execute('''
                INSERT INTO usuarios (nome, graduacao, pelotao, login, senha, nivel, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (data['nome'], data['nome'], data.get('pelotao'),
                  login, senha_hash, data['nivel'], 'ativo'))
            conn.commit()
            return jsonify({'success': True, 'message': 'Usuário criado com sucesso'})
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/usuarios/<int:id>', methods=['PUT'])
@login_required
@nivel_required(['DEV', 'SUB'])
def api_update_usuario(id):
    data = request.json
    
    with get_db() as conn:
        try:
            user = conn.execute('SELECT * FROM usuarios WHERE id = ?', (id,)).fetchone()
            if not user:
                return jsonify({'success': False, 'message': 'Usuário não encontrado'}), 404
            
            if data.get('senha') and data['senha'].strip():
                senha_hash = hashlib.sha256(data['senha'].encode()).hexdigest()
                conn.execute('''
                    UPDATE usuarios SET nome=?, graduacao=?, pelotao=?, nivel=?, senha=?
                    WHERE id=?
                ''', (data['nome'], data['nome'], data.get('pelotao'),
                      data['nivel'], senha_hash, id))
            else:
                conn.execute('''
                    UPDATE usuarios SET nome=?, graduacao=?, pelotao=?, nivel=?
                    WHERE id=?
                ''', (data['nome'], data['nome'], data.get('pelotao'),
                      data['nivel'], id))
            conn.commit()
            return jsonify({'success': True, 'message': 'Usuário atualizado com sucesso'})
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/usuarios/<int:id>', methods=['DELETE'])
@login_required
@nivel_required(['DEV'])
def api_delete_usuario(id):
    with get_db() as conn:
        try:
            user = conn.execute('SELECT * FROM usuarios WHERE id = ?', (id,)).fetchone()
            if not user:
                return jsonify({'success': False, 'message': 'Usuário não encontrado'}), 404
            
            if user['id'] == session['user_id']:
                return jsonify({'success': False, 'message': 'Você não pode excluir sua própria conta'}), 400
            
            movimentacoes = conn.execute('''
                SELECT COUNT(*) as count FROM movimentacoes WHERE usuario = ?
            ''', (user['nome'],)).fetchone()
            
            if movimentacoes['count'] > 0:
                conn.execute('UPDATE usuarios SET status = "inativo" WHERE id = ?', (id,))
                conn.commit()
                return jsonify({'success': True, 'message': 'Usuário desativado (possui movimentações no histórico)'})
            
            conn.execute('DELETE FROM usuarios WHERE id = ?', (id,))
            conn.commit()
            return jsonify({'success': True, 'message': 'Usuário excluído com sucesso'})
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/usuarios/<int:id>/status', methods=['PUT'])
@login_required
@nivel_required(['DEV', 'SUB'])
def api_update_usuario_status(id):
    data = request.json
    
    with get_db() as conn:
        conn.execute('UPDATE usuarios SET status = ? WHERE id = ?', (data['status'], id))
        conn.commit()
        return jsonify({'success': True, 'message': 'Status atualizado'})

# ============================================
# API BACKUP
# ============================================
@app.route('/api/backup/criar', methods=['POST'])
@login_required
@nivel_required(['DEV', 'SUB'])
def api_criar_backup():
    import shutil
    data_atual = datetime.now().strftime('%Y%m%d_%H%M%S')
    arquivo_backup = f'backup_{data_atual}.db'
    
    try:
        shutil.copy(DATABASE, arquivo_backup)
        tamanho = os.path.getsize(arquivo_backup)
        
        with get_db() as conn:
            conn.execute('''
                INSERT INTO backups (arquivo, data, usuario, tamanho)
                VALUES (?, ?, ?, ?)
            ''', (arquivo_backup, datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
                  session['user_nome'], f'{tamanho/1024:.2f} KB'))
            conn.commit()
        
        return jsonify({'success': True, 'arquivo': arquivo_backup})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/backup/listar', methods=['GET'])
@login_required
@nivel_required(['DEV', 'SUB'])
def api_listar_backups():
    with get_db() as conn:
        backups = conn.execute('SELECT * FROM backups ORDER BY id DESC').fetchall()
        return jsonify({'success': True, 'backups': [dict(b) for b in backups]})

@app.route('/api/backup/baixar/<nome>', methods=['GET'])
@login_required
@nivel_required(['DEV', 'SUB'])
def api_baixar_backup(nome):
    if os.path.exists(nome):
        return send_file(nome, as_attachment=True)
    return jsonify({'success': False, 'message': 'Arquivo não encontrado'}), 404

@app.route('/api/backup/excluir/<nome>', methods=['DELETE'])
@login_required
@nivel_required(['DEV', 'SUB'])
def api_excluir_backup(nome):
    try:
        if os.path.exists(nome):
            os.remove(nome)
            with get_db() as conn:
                conn.execute('DELETE FROM backups WHERE arquivo = ?', (nome,))
                conn.commit()
            return jsonify({'success': True})
        return jsonify({'success': False, 'message': 'Arquivo não encontrado'}), 404
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# ============================================
# API EXPORTAR/IMPORTAR BANCO
# ============================================
@app.route('/api/exportar_banco', methods=['GET'])
@login_required
@nivel_required(['DEV', 'SUB'])
def api_exportar_banco():
    try:
        data_atual = datetime.now().strftime('%Y%m%d_%H%M%S')
        arquivo_export = f'banco_exportado_{data_atual}.db'
        import shutil
        shutil.copy(DATABASE, arquivo_export)
        return send_file(arquivo_export, as_attachment=True, download_name=f'encmat_banco_{data_atual}.db')
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/importar_banco', methods=['POST'])
@login_required
@nivel_required(['DEV'])
def api_importar_banco():
    try:
        arquivo = request.files.get('banco')
        if not arquivo:
            return jsonify({'success': False, 'message': 'Nenhum arquivo enviado'}), 400
        
        arquivo.save(DATABASE)
        
        with get_db() as conn:
            now = datetime.now()
            conn.execute('''
                INSERT INTO logs_auditoria (usuario, data, hora, acao, ip, detalhes)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (session['user_nome'], now.strftime('%d/%m/%Y'), now.strftime('%H:%M:%S'),
                  'IMPORTAR_BANCO', request.remote_addr, 'Banco de dados importado'))
            conn.commit()
        
        return jsonify({'success': True, 'message': 'Banco importado com sucesso'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# ============================================
# API RESET BANCO
# ============================================
@app.route('/api/reset_banco', methods=['POST'])
@login_required
@nivel_required(['DEV'])
def api_reset_banco():
    try:
        if os.path.exists(DATABASE):
            os.remove(DATABASE)
        init_db()
        return jsonify({'success': True, 'message': 'Banco resetado com sucesso'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# ============================================
# API CONFIGURAÇÕES
# ============================================
@app.route('/api/alterar_senha', methods=['POST'])
@login_required
def api_alterar_senha():
    data = request.json
    senha_atual = data.get('senha_atual')
    nova_senha = data.get('nova_senha')
    
    if not senha_atual or not nova_senha:
        return jsonify({'success': False, 'message': 'Preencha todos os campos'}), 400
    
    senha_atual_hash = hashlib.sha256(senha_atual.encode()).hexdigest()
    
    with get_db() as conn:
        user = conn.execute('''
            SELECT * FROM usuarios WHERE id = ? AND senha = ?
        ''', (session['user_id'], senha_atual_hash)).fetchone()
        
        if not user:
            return jsonify({'success': False, 'message': 'Senha atual incorreta'}), 400
        
        nova_senha_hash = hashlib.sha256(nova_senha.encode()).hexdigest()
        conn.execute('UPDATE usuarios SET senha = ? WHERE id = ?', (nova_senha_hash, session['user_id']))
        conn.commit()
        return jsonify({'success': True, 'message': 'Senha alterada com sucesso'})

# ============================================
# API EXPORTAR RESERVA PELOTÃO PDF
# ============================================
@app.route('/api/exportar_reserva_pdf', methods=['POST'])
@login_required
def api_exportar_reserva_pdf():
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        import io
        from datetime import datetime
        
        data = request.json
        usuario = data.get('usuario', {})
        estoque = data.get('estoque', [])
        produtos = data.get('produtos', [])
        pelotao_filtro = data.get('pelotao_filtro', 'todos')
        data_exportacao = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
        
        # Filtrar estoque pelo pelotão selecionado
        if pelotao_filtro != 'todos':
            estoque = [item for item in estoque if item.get('pelotao') == pelotao_filtro]
        
        # Agrupar por pelotão
        pelotoes_agrupados = {}
        for item in estoque:
            pelotao = item.get('pelotao', 'Sem Pelotão')
            if pelotao not in pelotoes_agrupados:
                pelotoes_agrupados[pelotao] = []
            pelotoes_agrupados[pelotao].append(item)
        
        # Criar buffer para PDF
        buffer = io.BytesIO()
        
        # Criar documento com orientação paisagem
        doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), 
                               rightMargin=1*cm, leftMargin=1*cm,
                               topMargin=1*cm, bottomMargin=1*cm)
        
        styles = getSampleStyleSheet()
        story = []
        
        # Estilo para título
        titulo_style = ParagraphStyle(
            'TituloStyle',
            parent=styles['Heading1'],
            fontSize=16,
            textColor=colors.HexColor('#2d6a4f'),
            alignment=1,
            spaceAfter=20
        )
        
        # Estilo para subtítulo
        subtitulo_style = ParagraphStyle(
            'SubtituloStyle',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#4a6a4a'),
            alignment=1,
            spaceAfter=30
        )
        
        # Título
        story.append(Paragraph("ENC-MAT - Reserva dos Pelotões", titulo_style))
        story.append(Paragraph(f"Data da consulta: {data_exportacao}", subtitulo_style))
        story.append(Paragraph(f"Usuário: {usuario.get('nome', 'N/A')} - Nível: {usuario.get('nivel', 'N/A')}", subtitulo_style))
        
        if pelotao_filtro != 'todos':
            story.append(Paragraph(f"Pelotão filtrado: {pelotao_filtro}", subtitulo_style))
        story.append(Spacer(1, 10))
        
        # Para cada pelotão, criar uma tabela
        for pelotao, itens in sorted(pelotoes_agrupados.items()):
            # Cabeçalho do pelotão
            pelotao_style = ParagraphStyle(
                'PelotaoStyle',
                parent=styles['Heading2'],
                fontSize=12,
                textColor=colors.HexColor('#1a2c1a'),
                spaceBefore=15,
                spaceAfter=10
            )
            total_itens = sum(item.get('quantidade', 0) for item in itens)
            story.append(Paragraph(f"📦 {pelotao} (Total: {total_itens} itens)", pelotao_style))
            
            # Preparar dados da tabela
            tabela_dados = [
                ['Código', 'Material', 'Quantidade', 'Mínimo', 'Status Estoque', 'Status Item']
            ]
            
            for item in itens:
                # Buscar produto para obter mínimo
                produto = next((p for p in produtos if p.get('id') == item.get('material_id')), None)
                min_estoque = int(produto.get('quantidade_total', 0) * 0.3) if produto and produto.get('quantidade_total') else 10
                quantidade = item.get('quantidade', 0)
                
                # Determinar status do estoque
                if quantidade <= min_estoque:
                    status_estoque = "CRÍTICO"
                elif quantidade <= min_estoque * 1.5:
                    status_estoque = "ALERTA"
                else:
                    status_estoque = "NORMAL"
                
                status_item = item.get('status', 'DISPONIVEL')
                status_item_text = {
                    'DISPONIVEL': 'DISPONÍVEL',
                    'EM_USO': 'EM USO',
                    'MANUTENCAO': 'MANUTENÇÃO',
                    'EXTRAVIADO': 'EXTRAVIADO'
                }.get(status_item, status_item)
                
                tabela_dados.append([
                    item.get('codigo', '-'),
                    item.get('material_nome', '-'),
                    str(quantidade),
                    str(min_estoque),
                    status_estoque,
                    status_item_text
                ])
            
            # Criar tabela
            tabela = Table(tabela_dados, repeatRows=1)
            tabela.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2d6a4f')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('ALIGN', (2, 0), (2, -1), 'CENTER'),
                ('ALIGN', (3, 0), (3, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('TOPPADDING', (0, 0), (-1, 0), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#c0d4c0')),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ffffff')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#f5faf5'), colors.white]),
            ]))
            
            story.append(tabela)
            story.append(Spacer(1, 15))
        
        # Rodapé com total geral
        total_geral = sum(item.get('quantidade', 0) for item in estoque)
        rodape_style = ParagraphStyle(
            'RodapeStyle',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.HexColor('#4a6a4a'),
            alignment=1,
            spaceBefore=20
        )
        story.append(Paragraph(f"Total geral de materiais nos pelotões: {total_geral} itens", rodape_style))
        story.append(Paragraph("ENC-MAT - Sistema de Controle de Estoque", rodape_style))
        
        # Gerar PDF
        doc.build(story)
        buffer.seek(0)
        
        return send_file(
            buffer,
            as_attachment=True,
            download_name=f'reserva_pelotoes_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf',
            mimetype='application/pdf'
        )
    except ImportError:
        return jsonify({'success': False, 'message': 'Biblioteca reportlab não instalada. Execute: pip install reportlab'}), 500
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Erro ao gerar PDF: {str(e)}'}), 500

# ============================================
# MAIN
# ============================================
if __name__ == '__main__':
    import sys
    
    recriar_banco = '--reset' in sys.argv
    
    if recriar_banco:
        print("🔄 Recriando banco de dados...")
        try:
            if os.path.exists(DATABASE):
                for tentativa in range(3):
                    try:
                        os.remove(DATABASE)
                        print(f"🗑️ Banco antigo removido (tentativa {tentativa + 1})")
                        break
                    except PermissionError:
                        if tentativa < 2:
                            print(f"⚠️ Banco em uso, tentando novamente em 2 segundos... (tentativa {tentativa + 1}/3)")
                            import time
                            time.sleep(2)
                        else:
                            print(f"❌ Não foi possível remover o banco. Ele pode estar em uso.")
                            resposta = input("Deseja continuar com o banco existente? (s/N): ")
                            if resposta.lower() != 's':
                                sys.exit(1)
        except Exception as e:
            print(f"❌ Erro ao remover banco: {e}")
    
    init_db()
    
    print('=' * 60)
    print('ENC-MAT - Sistema de Controle de Estoque')
    print('=' * 60)
    print('✅ Servidor iniciado com sucesso!')
    print('📍 Acesse: http://localhost:5000')
    print('')
    print('👑 USUÁRIOS DE ACESSO:')
    print('   dev / dev123     → Desenvolvedor (acesso total)')
    print('   sub / sub123     → Sub Tenente (fiscalização)')
    print('   pelotao1 / 123   → 1º Pelotão')
    print('   pelotao2 / 123   → 2º Pelotão')
    print('   pelotao3 / 123   → 3º Pelotão')
    print('   leitura / leitura123 → Somente leitura')
    print('=' * 60)
    print('')
    print('💡 Dica: Use "python app.py --reset" para recriar o banco de dados do zero')
    print('')
    
    app.run(debug=True, host='0.0.0.0', port=5000)