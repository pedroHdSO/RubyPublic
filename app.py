from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime
from functools import wraps
from unidecode import unidecode
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

# =============================================================================
# CONFIGURAÇÃO INICIAL DA APLICAÇÃO FLASK
# =============================================================================

app = Flask(__name__, template_folder='templates')

app.secret_key = os.environ.get('SECRET_KEY', 'ruby_alignment_kanban_secret_key_2024')

app.config['MYSQL_HOST'] = os.environ.get('MYSQL_HOST', 'yamabiko.proxy.rlwy.net')
app.config['MYSQL_PORT'] = int(os.environ.get('MYSQL_PORT', 25072))
app.config['MYSQL_USER'] = os.environ.get('MYSQL_USER', 'root')
app.config['MYSQL_PASSWORD'] = os.environ.get('MYSQL_PASSWORD', 'vAUtAghOOjnBQNAgtgbKYjKgxrxypBWN')
app.config['MYSQL_DB'] = os.environ.get('MYSQL_DB', 'railway')
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'

mysql = MySQL(app)

DEFAULT_PASSWORD = "cah@123"

# =============================================================================
# DECORATORS E FUNÇÕES AUXILIARES
# =============================================================================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Autenticação necessária'}), 401
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('user_role') != 'ADMINISTRADOR':
            return jsonify({'error': 'Acesso negado. Requer privilégios de administrador.'}), 403
        return f(*args, **kwargs)
    return decorated_function

def solicitante_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('user_role') not in ['SOLICITANTE', 'ADMINISTRADOR']:
            return jsonify({'error': 'Acesso negado. Apenas para solicitantes ou administradores.'}), 403
        return f(*args, **kwargs)
    return decorated_function

def colaborador_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('user_role') not in ['COLABORADOR', 'SOLICITANTE', 'ADMINISTRADOR']:
            return jsonify({'error': 'Acesso negado.'}), 403
        return f(*args, **kwargs)
    return decorated_function

def log_change(user, action, details):
    cur = None
    try:
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO Logs (timestamp, usuario, acao, detalhes) VALUES (%s, %s, %s, %s)",
                      (datetime.now(), user, action, details))
        mysql.connection.commit()
    except Exception as e:
        print(f"ERRO CRÍTICO: Falha ao registrar log no banco de dados: {e}")
    finally:
        if cur: cur.close()

def generate_ruby_email(full_name, cursor):
    parts = unidecode(full_name.lower()).replace('.', '').split()
    base_email = f"{parts[0]}.{parts[-1]}" if len(parts) >= 2 else parts[0]
    final_email = f"{base_email}@ruby.com"
    
    cursor.execute("SELECT email FROM Colaborador WHERE email = %s", (final_email,))
    if not cursor.fetchone():
        return final_email
        
    i = 1
    while True:
        numbered_email = f"{base_email}{i:02d}@ruby.com"
        cursor.execute("SELECT email FROM Colaborador WHERE email = %s", (numbered_email,))
        if not cursor.fetchone():
            return numbered_email
        i += 1

# =============================================================================
# ROTAS DE PÁGINAS E AUTENTICAÇÃO
# =============================================================================

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        cur = None
        try:
            email = request.form['username']
            password = request.form['password']
            cur = mysql.connection.cursor()
            cur.execute("SELECT a.idADM, a.nome, a.email, a.senha, a.status, na.nivel as perfil, a.idColaborador FROM ADM a JOIN NivelAcesso na ON a.idNivelAcesso = na.idNivelAcesso WHERE a.email = %s", (email,))
            user = cur.fetchone()
            if user:
                is_valid = (user['status'] == 'TEMP' and user['senha'] == password) or \
                           (user['status'] != 'TEMP' and check_password_hash(user['senha'], password))
                if is_valid:
                    session.permanent = True
                    session['user_id'] = user['idADM']
                    session['user_name'] = user['nome']
                    session['user_email'] = user['email']
                    session['user_role'] = user['perfil'].upper()
                    session['user_colaborador_id'] = user['idColaborador']

                    if user['status'] == 'TEMP' and session['user_role'] not in ['ADMIN']:
                        return redirect('/change_password_first')

                    log_change(user['nome'], 'LOGIN', 'Login bem-sucedido.')
                    return redirect(url_for('dashboard'))
            return render_template('login.html', error='E-mail ou senha inválidos.')
        except Exception as e:
            print(f"Erro no login: {e}")
            return render_template('login.html', error='Erro interno do servidor.')
        finally:
            if cur: cur.close()
    return render_template('login.html')




# =========================================================
#                           OLD
# =========================================================
# @app.route('/change_password_first', methods=['POST'])
# @login_required
# def change_password_first():
    # new_password = request.form['new_password']
    # hashed_password = generate_password_hash(new_password)
    # cur = mysql.connection.cursor()
    # cur.execute("UPDATE ADM SET senha = %s, status = 'OK' WHERE idADM = %s", (hashed_password, session['user_id']))
    # mysql.connection.commit()
    # cur.close()
    # log_change(session['user_name'], 'SENHA ALTERADA', 'Senha de primeiro acesso atualizada.')
    # return jsonify({'success': True, 'message': 'Senha alterada com sucesso!'})




# =========================================================
#                           NEW
# =========================================================
@app.route('/change_password_first', methods=['GET', 'POST'])
@login_required
def change_password_first():
    if request.method == 'POST':
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        # Verifica se as senhas conferem
        if new_password != confirm_password:
            return render_template(
                'change_password_first.html',
                error='As senhas não coincidem. Tente novamente.'
            )

        try:
            hashed_password = generate_password_hash(new_password)
            cur = mysql.connection.cursor()
            cur.execute("""
                UPDATE ADM
                SET senha = %s, status = 'OK'
                WHERE idADM = %s
            """, (hashed_password, session['user_id']))
            mysql.connection.commit()
            cur.close()

            log_change(
                session['user_name'],
                'SENHA ALTERADA',
                'Senha de primeiro acesso atualizada.'
            )

            # Redireciona após o sucesso
            return redirect(url_for('dashboard'))

        except Exception as e:
            print(f"Erro ao atualizar senha: {e}")
            return render_template(
                'change_password_first.html',
                error='Erro ao atualizar a senha. Tente novamente mais tarde.'
            )

    # Se for GET, apenas renderiza a página
    return render_template('change_password_first.html')

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

@app.route('/logout')
def logout():
    log_change(session.get('user_name', 'Desconhecido'), 'LOGOUT', 'Sessão encerrada.')
    session.clear()
    return redirect(url_for('login'))

# ADICIONE ESTE NOVO BLOCO DE CÓDIGO AQUI
@app.route('/api/session', methods=['GET'])
@login_required
def get_session_data():
    """Retorna os dados da sessão do usuário atual para o frontend."""
    if 'user_id' in session:
        return jsonify({
            'user_id': session['user_id'],
            'user_name': session['user_name'],
            'user_role': session['user_role'],
            'user_colaborador_id': session['user_colaborador_id']
        })
    return jsonify({'error': 'Sessão não encontrada'}), 404

# =============================================================================
# API - GERENCIAMENTO DE USUÁRIOS
# =============================================================================

@app.route('/api/users', methods=['GET'])
@login_required
@admin_required
def get_users():
    cur = mysql.connection.cursor()
    cur.execute("SELECT a.idADM, a.nome, c.nome as nome_completo, a.email, n.nivel as perfil FROM ADM a JOIN NivelAcesso n ON a.idNivelAcesso = n.idNivelAcesso JOIN Colaborador c ON a.idColaborador = c.idColaborador ORDER BY a.nome")
    users = cur.fetchall()
    cur.close()
    return jsonify({'data': users})

@app.route('/api/users/<int:user_id>', methods=['GET'])
@login_required
@admin_required
def get_user_details(user_id):
    cur = None
    try:
        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT a.idADM, a.nome as nome_login, c.email as corporate_email, na.nivel as perfil,
                   c.nome as nome_completo, c.telefone, c.dataAdmissao, c.idColaborador
            FROM ADM a
            JOIN NivelAcesso na ON a.idNivelAcesso = na.idNivelAcesso
            JOIN Colaborador c ON a.idColaborador = c.idColaborador
            WHERE a.idADM = %s
        """, (user_id,))
        user = cur.fetchone()
        if not user: return jsonify({'error': 'Usuário não encontrado.'}), 404
        if user['dataAdmissao']: user['dataAdmissao'] = user['dataAdmissao'].strftime('%Y-%m-%d')
        
        cur.execute("SELECT habilidade FROM HardSkill WHERE idColaborador = %s", (user['idColaborador'],))
        user['skills'] = [row['habilidade'] for row in cur.fetchall()]
        
        return jsonify({'data': user})
    except Exception as e:
        print(f"Erro em get_user_details: {e}")
        return jsonify({'error': 'Erro interno ao buscar detalhes do usuário.'}), 500
    finally:
        if cur: cur.close()

@app.route('/api/users', methods=['POST'])
@login_required
@admin_required
def add_user():
    cur = None
    try:
        data = request.get_json()
        required = ['nome_login', 'nome_completo', 'role', 'admission_date', 'phone']
        if not all(key in data for key in required):
            return jsonify({'error': 'Todos os campos de usuário são obrigatórios.'}), 400
        
        cur = mysql.connection.cursor()
        corporate_email = generate_ruby_email(data['nome_completo'], cur)
        role_upper = data['role'].upper()
        
        cargo_map = {'ADMINISTRADOR': 1, 'SOLICITANTE': 2, 'COLABORADOR': 3}
        cur.execute("SELECT idDepartamento FROM Departamento WHERE nome = 'TI'")
        departamento = cur.fetchone()
        cur.execute("SELECT idStatusColaborador FROM StatusColaborador WHERE status = 'ativo'")
        status = cur.fetchone()

        if not all([departamento, status]):
            return jsonify({'error': 'Erro de configuração: Departamento ou Status não encontrado.'}), 500
        
        cur.execute("INSERT INTO Colaborador (nome, email, telefone, dataAdmissao, idCargo, idDepartamento, idStatusColaborador) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (data['nome_completo'], corporate_email, data['phone'], data['admission_date'], cargo_map.get(role_upper), departamento['idDepartamento'], status['idStatusColaborador']))
        colaborador_id = cur.lastrowid

        skills = data.get('skills', [])
        if skills:
            cur.executemany("INSERT INTO HardSkill (idColaborador, habilidade) VALUES (%s, %s)", [(colaborador_id, skill) for skill in skills])

        nivel_acesso_map = {'ADMINISTRADOR': 1, 'SOLICITANTE': 2, 'COLABORADOR': 3}
        nivel_acesso_id = nivel_acesso_map.get(role_upper)
        
        cur.execute("INSERT INTO ADM (nome, email, senha, dataCadastro, idColaborador, idNivelAcesso, status) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (data['nome_login'], corporate_email, DEFAULT_PASSWORD, datetime.now(), colaborador_id, nivel_acesso_id, 'TEMP'))
        
        mysql.connection.commit()
        log_change(session['user_name'], 'USUÁRIO ADICIONADO', f"Usuário: {data['nome_completo']}, E-mail: {corporate_email}")
        return jsonify({'success': True, 'message': f'Usuário "{data["nome_completo"]}" criado com o e-mail {corporate_email}!'}), 201

    except Exception as e:
        if cur: mysql.connection.rollback()
        print(f"Erro em add_user: {e}")
        return jsonify({'error': f'Erro interno no servidor: {str(e)}'}), 500
    finally:
        if cur: cur.close()

@app.route('/api/users/<int:user_id>', methods=['PUT'])
@login_required
@admin_required
def update_user(user_id):
    cur = None
    try:
        data = request.get_json()
        cur = mysql.connection.cursor()
        cur.execute("SELECT idColaborador FROM ADM WHERE idADM = %s", (user_id,))
        user_adm = cur.fetchone()
        if not user_adm: return jsonify({'error': 'Usuário não encontrado.'}), 404
        colaborador_id = user_adm['idColaborador']

        cur.execute("UPDATE Colaborador SET nome = %s, telefone = %s, dataAdmissao = %s WHERE idColaborador = %s",
                    (data['nome_completo'], data['phone'], data['admission_date'], colaborador_id))

        cur.execute("DELETE FROM HardSkill WHERE idColaborador = %s", (colaborador_id,))
        skills = data.get('skills', [])
        if skills:
            cur.executemany("INSERT INTO HardSkill (idColaborador, habilidade) VALUES (%s, %s)", [(colaborador_id, skill) for skill in skills])

        role_upper = data['role'].upper()
        nivel_acesso_map = {'ADMINISTRADOR': 1, 'SOLICITANTE': 2, 'COLABORADOR': 3}
        nivel_acesso_id = nivel_acesso_map.get(role_upper)
        cur.execute("UPDATE ADM SET nome = %s, idNivelAcesso = %s WHERE idADM = %s", (data['nome_login'], nivel_acesso_id, user_id))
        
        mysql.connection.commit()
        log_change(session['user_name'], 'USUÁRIO ATUALIZADO', f"ID: {user_id}")
        return jsonify({'success': True, 'message': 'Usuário atualizado com sucesso!'})

    except Exception as e:
        if cur: mysql.connection.rollback()
        print(f"Erro em update_user: {e}")
        return jsonify({'error': f'Erro interno no servidor: {str(e)}'}), 500
    finally:
        if cur: cur.close()

@app.route('/api/users/<int:user_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_user(user_id):
    cur = None
    try:
        if user_id == session.get('user_id'):
            return jsonify({'error': 'Você não pode deletar sua própria conta.'}), 403
        cur = mysql.connection.cursor()
        cur.execute("SELECT nome, idColaborador FROM ADM WHERE idADM = %s", (user_id,))
        user = cur.fetchone()
        if not user: return jsonify({'error': 'Usuário não encontrado.'}), 404
        
        cur.execute("DELETE FROM HardSkill WHERE idColaborador = %s", (user['idColaborador'],))
        cur.execute("DELETE FROM ADM WHERE idADM = %s", (user_id,))
        # O registro em Colaborador é mantido para integridade histórica
        mysql.connection.commit()
        log_change(session['user_name'], 'USUÁRIO DELETADO', f"Usuário '{user['nome']}' (ID: {user_id}) foi deletado.")
        return jsonify({'success': True, 'message': f'Usuário "{user["nome"]}" deletado com sucesso!'})
    except Exception as e:
        if cur: mysql.connection.rollback()
        print(f"Erro em delete_user: {e}")
        return jsonify({'error': 'Erro interno no servidor ao deletar usuário.'}), 500
    finally:
        if cur: cur.close()

# =============================================================================
# API - GERENCIAMENTO DE PROJETOS (DEMANDAS)
# =============================================================================

@app.route('/api/projects', methods=['GET'])
@login_required
def get_projects():
    cur = None
    try:
        cur = mysql.connection.cursor()
        query = """
            SELECT 
                d.idDemandas, d.titulo, d.descricao, d.dataAbertura, d.dataConclusao,
                s.status as status_nome, 
                p.prioridade as urgencia,
                sol.nome as solicitante_nome, 
                CONCAT(d.estagiario_responsavel, IF(d.estagiario_corresponsavel != '', CONCAT(', ', d.estagiario_corresponsavel), '')) as colaborador_nome,
                d.dataLimite, d.supervisor_responsavel, d.objetivo
            FROM Demandas d
            LEFT JOIN StatusDemanda s ON d.idStatusDemanda = s.idStatusDemanda
            LEFT JOIN PrioridadeDemanda p ON d.idPrioridadeDemanda = p.idPrioridadeDemanda
            LEFT JOIN Solicitante sol ON d.idSolicitante = sol.idSolicitante
            WHERE 1=1
        """
        params = []
        user_role = session.get('user_role')
        if user_role == 'SOLICITANTE':
            query += " AND sol.idColaborador = %s"
            params.append(session.get('user_colaborador_id'))
        elif user_role == 'COLABORADOR':
            query += " AND (d.idColaborador = %s OR d.estagiario_corresponsavel LIKE %s)"
            user_name_like = f"%{session.get('user_name')}%"
            params.extend([session.get('user_colaborador_id'), user_name_like])
        query += " ORDER BY d.dataAbertura DESC"
        cur.execute(query, tuple(params))
        projects = cur.fetchall()
        for p in projects:
            if isinstance(p.get('dataAbertura'), datetime): p['dataAbertura'] = p['dataAbertura'].strftime('%d/%m/%Y')
            if isinstance(p.get('dataLimite'), datetime): p['dataLimite'] = p['dataLimite'].strftime('%d/%m/%Y')
            if isinstance(p.get('dataConclusao'), datetime): p['dataConclusao'] = p['dataConclusao'].strftime('%d/%m/%Y')
        return jsonify({'data': projects})
    except Exception as e:
        print(f"Erro em get_projects: {e}")
        return jsonify({'error': f'Erro interno do servidor: {str(e)}'}), 500
    finally:
        if cur: cur.close()

@app.route('/api/projects', methods=['POST'])
@login_required
@solicitante_required
def create_project():
    cur = None
    try:
        data = request.get_json()
        if not data.get('titulo') or not data.get('descricao'):
            return jsonify({'error': 'Título e Descrição do projeto são obrigatórios.'}), 400
        
        cur = mysql.connection.cursor()
        
        # Obter IDs necessários
        cur.execute("SELECT idStatusDemanda FROM StatusDemanda WHERE status = 'NÃO INICIADO'")
        status_result = cur.fetchone()
        if not status_result:
            return jsonify({'error': 'Status "NÃO INICIADO" não encontrado.'}), 500
        status_id = status_result['idStatusDemanda']
        
        cur.execute("SELECT idPrioridadeDemanda FROM PrioridadeDemanda WHERE prioridade = 'Média'")
        prioridade_result = cur.fetchone()
        if not prioridade_result:
            return jsonify({'error': 'Prioridade "Média" não encontrada.'}), 500
        prioridade_id = prioridade_result['idPrioridadeDemanda']
        
        # SOLUÇÃO MELHOR: Buscar solicitante existente ou criar com email único
        cur.execute("SELECT idSolicitante FROM Solicitante WHERE idColaborador = %s", (session['user_colaborador_id'],))
        solicitante = cur.fetchone()
        solicitante_id = solicitante['idSolicitante'] if solicitante else None
        
        if not solicitante_id:
            # Buscar dados do colaborador
            cur.execute("SELECT nome, email FROM Colaborador WHERE idColaborador = %s", (session['user_colaborador_id'],))
            colaborador_result = cur.fetchone()
            
            if colaborador_result:
                colaborador_nome = colaborador_result['nome']
                colaborador_email = colaborador_result['email']
            else:
                colaborador_nome = session['user_name']
                colaborador_email = session['user_email']
            
            # Criar email único para solicitante (limitando tamanho)
            base_name = unidecode(colaborador_nome.lower().replace(' ', '.').replace('.', ''))
            # Limitar o nome base para evitar emails muito longos
            if len(base_name) > 20:
                base_name = base_name[:20]
                
            solicitante_email = f"{base_name}.solicitante@ruby.com"
            
            # Verificar se o email já existe e gerar um único se necessário
            cur.execute("SELECT idSolicitante FROM Solicitante WHERE email = %s", (solicitante_email,))
            if cur.fetchone():
                # Se já existir, usar um email numerado
                i = 1
                while True:
                    numbered_email = f"{base_name}.solicitante{i:02d}@ruby.com"
                    # Garantir que o email não ultrapasse o limite
                    if len(numbered_email) > 100:
                        numbered_email = numbered_email[:100]
                    cur.execute("SELECT idSolicitante FROM Solicitante WHERE email = %s", (numbered_email,))
                    if not cur.fetchone():
                        solicitante_email = numbered_email
                        break
                    i += 1
                    if i > 99:  # Prevenir loop infinito
                        solicitante_email = f"{session['user_id']}.solicitante@ruby.com"
                        break
            
            # Garantir que o email final não ultrapasse o limite
            if len(solicitante_email) > 100:
                solicitante_email = solicitante_email[:100]
            
            print(f"📧 Criando solicitante com email: {solicitante_email}")  # Para debug
            
            cur.execute("INSERT INTO Solicitante (nome, email, dataCadastro, idColaborador) VALUES (%s, %s, %s, %s)",
                        (colaborador_nome, solicitante_email, datetime.now(), session['user_colaborador_id']))
            solicitante_id = cur.lastrowid
        
        # Converter data do formato dd/mm/yyyy para yyyy-mm-dd
        data_limite = None
        if data.get('dataLimite'):
            try:
                # Converte de dd/mm/yyyy para yyyy-mm-dd
                data_parts = data['dataLimite'].split('/')
                if len(data_parts) == 3:
                    data_limite = f"{data_parts[2]}-{data_parts[1]}-{data_parts[0]}"
            except Exception as e:
                print(f"Erro ao converter data: {e}")
                return jsonify({'error': 'Formato de data inválido. Use dd/mm/aaaa.'}), 400
        
        # Inserir projeto com TODOS os campos obrigatórios
        cur.execute("""
            INSERT INTO Demandas (
                titulo, descricao, dataAbertura, dataLimite, idSolicitante, 
                idStatusDemanda, idPrioridadeDemanda, supervisor_responsavel, objetivo,
                idColaborador, estagiario_responsavel, estagiario_corresponsavel,
                reuniao_requisitos, coleta_preparacao_dados, criacao_relatorio_dashboard,
                validacao_refinamento, documentacao, observacao,
                inicio_projeto, previsao_termino, dataConclusao, periodo
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            data['titulo'], 
            data['descricao'], 
            datetime.now(),  # dataAbertura
            data_limite,  # dataLimite (já convertida)
            solicitante_id,  # idSolicitante
            status_id,  # idStatusDemanda
            prioridade_id,  # idPrioridadeDemanda
            data.get('supervisor_responsavel', ''),  # supervisor_responsavel
            data.get('objetivo', ''),  # objetivo
            None,  # idColaborador (pode ser NULL inicialmente)
            '',  # estagiario_responsavel
            '',  # estagiario_corresponsavel
            'NÃO REALIZADO',  # reuniao_requisitos
            'NÃO REALIZADO',  # coleta_preparacao_dados
            'NÃO REALIZADO',  # criacao_relatorio_dashboard
            'NÃO REALIZADO',  # validacao_refinamento
            'NÃO REALIZADO',  # documentacao
            '',  # observacao
            None,  # inicio_projeto
            None,  # previsao_termino
            None,   # dataConclusao
            ''  # periodo
        ))
        
        mysql.connection.commit()
        log_change(session['user_name'], 'PROJETO CADASTRADO', f"Projeto: {data['titulo']}")
        return jsonify({'success': True, 'message': 'Projeto cadastrado com sucesso!'}), 201
        
    except Exception as e:
        mysql.connection.rollback()
        print(f"Erro em create_project: {e}")
        import traceback
        print(f"Traceback completo: {traceback.format_exc()}")
        return jsonify({'error': f'Erro ao cadastrar projeto: {str(e)}'}), 500
    finally:
        if cur: cur.close()
            
@app.route('/api/projects/<int:project_id>/urgency', methods=['PUT'])
@login_required
@solicitante_required
def update_urgency(project_id):
    cur = None
    try:
        data = request.get_json()
        if not data.get('urgencia'):
            return jsonify({'error': 'O campo urgência é obrigatório.'}), 400
        
        cur = mysql.connection.cursor()
        
        cur.execute("SELECT idPrioridadeDemanda FROM PrioridadeDemanda WHERE prioridade = %s", (data['urgencia'],))
        prioridade = cur.fetchone()
        if not prioridade:
            return jsonify({'error': 'Valor de urgência inválido.'}), 400
        
        query_args = [project_id]
        permission_query = "SELECT d.titulo FROM Demandas d "
        if session.get('user_role') != 'ADMINISTRADOR':
            permission_query += "JOIN Solicitante s ON d.idSolicitante = s.idSolicitante WHERE d.idDemandas = %s AND s.idColaborador = %s"
            query_args.append(session.get('user_colaborador_id'))
        else:
            permission_query += "WHERE d.idDemandas = %s"
        
        cur.execute(permission_query, tuple(query_args))
        project = cur.fetchone()
        if not project:
            return jsonify({'error': 'Projeto não encontrado ou você não tem permissão para alterá-lo.'}), 404
            
        cur.execute("UPDATE Demandas SET idPrioridadeDemanda = %s WHERE idDemandas = %s", 
                      (prioridade['idPrioridadeDemanda'], project_id))
        mysql.connection.commit()
        
        log_change(session['user_name'], 'URGÊNCIA ATUALIZADA', f"Urgência do projeto '{project['titulo']}' alterada para '{data['urgencia']}'")
        return jsonify({'success': True, 'message': 'Urgência do projeto atualizada com sucesso!'})
    except Exception as e:
        if cur: mysql.connection.rollback()
        print(f"Erro em update_urgency: {e}")
        return jsonify({'error': 'Erro interno ao atualizar a urgência.'}), 500
    finally:
        if cur: cur.close()


@app.route('/api/projects/<int:project_id>/adhere', methods=['POST'])
@login_required
@solicitante_required
def adhere_to_project(project_id):
    cur = None
    try:
        data = request.get_json()
        required = ['integrantes', 'inicio_projeto', 'previsao_termino']
        if not all(field in data and data[field] for field in required) or not data['integrantes']:
            return jsonify({'error': 'Todos os campos (*) são obrigatórios.'}), 400
        
        cur = mysql.connection.cursor()

        integrantes_nomes = data['integrantes']
        responsavel_nome = integrantes_nomes[0]
        coresponsaveis_nomes = ", ".join(integrantes_nomes[1:])

        cur.execute("SELECT idColaborador FROM Colaborador WHERE nome = %s", (responsavel_nome,))
        responsavel = cur.fetchone()
        if not responsavel:
            return jsonify({'error': f"Colaborador '{responsavel_nome}' não encontrado."}), 404

        cur.execute("SELECT idStatusDemanda FROM StatusDemanda WHERE status = 'EM ANDAMENTO'")
        status_andamento = cur.fetchone()
        
        cur.execute("""
            UPDATE Demandas SET 
                idColaborador = %s,
                estagiario_responsavel = %s,
                estagiario_corresponsavel = %s,
                inicio_projeto = %s,
                previsao_termino = %s,
                idStatusDemanda = %s
            WHERE idDemandas = %s
        """, (
            responsavel['idColaborador'],
            responsavel_nome,
            coresponsaveis_nomes,
            data['inicio_projeto'],
            data['previsao_termino'],
            status_andamento['idStatusDemanda'],
            project_id
        ))
        
        mysql.connection.commit()
        log_change(session['user_name'], 'ADESÃO REALIZADA', f"Projeto {project_id} atribuído a {responsavel_nome}")
        return jsonify({'success': True, 'message': 'Adesão ao projeto realizada com sucesso!'})
    except Exception as e:
        if cur: mysql.connection.rollback()
        print(f"Erro em adhere_to_project: {e}")
        return jsonify({'error': 'Erro interno ao processar a adesão ao projeto.'}), 500
    finally:
        if cur: cur.close()

@app.route('/api/projects/<int:project_id>/status', methods=['PUT'])
@login_required
@colaborador_required
def update_progress(project_id):
    cur = None
    try:
        data = request.get_json()
        cur = mysql.connection.cursor()

        permission_query = "SELECT idDemandas, titulo FROM Demandas WHERE idDemandas = %s"
        query_params = [project_id]
        if session.get('user_role') != 'ADMINISTRADOR':
            permission_query += " AND (idColaborador = %s OR idSolicitante = (SELECT idSolicitante FROM Solicitante WHERE idColaborador = %s))"
            query_params.extend([session.get('user_colaborador_id'), session.get('user_colaborador_id')])
        
        cur.execute(permission_query, tuple(query_params))
        project = cur.fetchone()
        if not project:
            return jsonify({'error': 'Projeto não encontrado ou você não tem permissão para alterá-lo.'}), 404

        update_fields, update_values = [], []
        field_map = {
            'reuniao_requisitos': 'reuniao_requisitos', 'coleta_preparacao_dados': 'coleta_preparacao_dados',
            'criacao_relatorio_dashboard': 'criacao_relatorio_dashboard', 'validacao_refinamento': 'validacao_refinamento',
            'documentacao': 'documentacao', 'observacao': 'observacao'
        }
        
        for json_field, db_column in field_map.items():
            if json_field in data:
                update_fields.append(f"{db_column} = %s")
                update_values.append(data[json_field])
        
        if 'status_geral' in data:
            cur.execute("SELECT idStatusDemanda FROM StatusDemanda WHERE status = %s", (data['status_geral'],))
            status_result = cur.fetchone()
            if status_result:
                update_fields.append("idStatusDemanda = %s")
                update_values.append(status_result['idStatusDemanda'])
        
        if 'dataConclusao' in data and data['dataConclusao']:
            update_fields.append("dataConclusao = %s")
            update_values.append(data['dataConclusao'])

        if not update_fields:
            return jsonify({'message': 'Nenhum dado válido para atualização foi fornecido.'}), 400
            
        update_query = f"UPDATE Demandas SET {', '.join(update_fields)} WHERE idDemandas = %s"
        update_values.append(project_id)
        
        cur.execute(update_query, tuple(update_values))
        mysql.connection.commit()
        
        log_change(session['user_name'], 'ANDAMENTO ATUALIZADO', f"Andamento do projeto '{project['titulo']}' foi atualizado.")
        return jsonify({'success': True, 'message': 'Andamento do projeto atualizado com sucesso!'})
    
    except Exception as e:
        if cur: mysql.connection.rollback()
        print(f"Erro em update_progress: {e}")
        return jsonify({'error': 'Erro interno ao atualizar o andamento do projeto.'}), 500
    finally:
        if cur: cur.close()

# =============================================================================
# API - MACHINE LEARNING
# =============================================================================

@app.route('/api/project/<int:project_id>/adherence', methods=['GET'])
@login_required
@solicitante_required 
def get_project_adherence(project_id):
    suggestions = calcular_aderencia_projeto(project_id, mysql)
    if suggestions is None:
        return jsonify({'error': 'Erro ao calcular aderência.'}), 500
    return jsonify(suggestions)

# def calcular_aderencia_projeto(project_id, db_connection):
#     cur = None
#     try:
#         cur = db_connection.connection.cursor()
#         cur.execute("SELECT objetivo, descricao FROM Demandas WHERE idDemandas = %s", (project_id,))
#         project_data = cur.fetchone()
#         if not project_data or (not project_data['objetivo'] and not project_data['descricao']): return []
#         project_requirements = f"{project_data['objetivo'] or ''} {project_data['descricao'] or ''}"
#         cur.execute("SELECT c.idColaborador, c.nome, GROUP_CONCAT(DISTINCT hs.habilidade SEPARATOR ' ') as habilidades FROM Colaborador c LEFT JOIN HardSkill hs ON c.idColaborador = hs.idColaborador GROUP BY c.idColaborador, c.nome")
#         colaboradores = cur.fetchall()
#         if not colaboradores: return []
#         colab_data = [{'id': c['idColaborador'], 'nome': c['nome'], 'habilidades': c['habilidades'] or ''} for c in colaboradores]
#         all_texts = [project_requirements] + [c['habilidades'] for c in colab_data]
#         vectorizer = TfidfVectorizer()
#         tfidf_matrix = vectorizer.fit_transform(all_texts)
#         similarities = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:]).flatten()
#         results = [{'id': colab['id'], 'nome': colab['nome'], 'aderencia': round(sim * 100, 2)} for colab, sim in zip(colab_data, similarities)]
#         results.sort(key=lambda x: x['aderencia'], reverse=True)
#         return results
#     except Exception as e:
#         print(f"ERRO CRÍTICO em calcular_aderencia_projeto: {e}")
#         return None
#     finally:
#         if cur: cur.close()

def calcular_aderencia_projeto(project_id, db_connection):
    cur = None
    try:
        cur = db_connection.connection.cursor()
        
        # Buscar dados do projeto
        cur.execute("SELECT objetivo, descricao FROM Demandas WHERE idDemandas = %s", (project_id,))
        project_data = cur.fetchone()
        
        if not project_data or (not project_data['objetivo'] and not project_data['descricao']): 
            # Se não há dados do projeto, retorna apenas colaboradores (não administradores/solicitantes)
            cur.execute("""
                SELECT c.idColaborador, c.nome FROM Colaborador c
                LEFT JOIN ADM a ON a.idColaborador = c.idColaborador 
                WHERE a.idNivelAcesso = 3
            """)
            colaboradores = cur.fetchall()
            return [{'id': c['idColaborador'], 'nome': c['nome'], 'aderencia': 0.0, 'habilidades_comuns': []} for c in colaboradores]
        
        # Extrair habilidades específicas da descrição do projeto
        project_text = f"{project_data['objetivo'] or ''} {project_data['descricao'] or ''}"
        
        # Procurar por habilidades na descrição (padrão: "Habilidades Desejadas: ...")
        import re
        habilidades_match = re.search(r'Habilidades Desejadas:\s*(.+)', project_text, re.IGNORECASE)
        
        # Buscar apenas colaboradores (não administradores/solicitantes)
        cur.execute("""
            SELECT c.idColaborador, c.nome, 
                GROUP_CONCAT(DISTINCT hs.habilidade SEPARATOR ', ') as habilidades 
            FROM Colaborador c 
            LEFT JOIN HardSkill hs ON c.idColaborador = hs.idColaborador 
            INNER JOIN ADM adm ON c.idColaborador = adm.idColaborador
            WHERE adm.idNivelAcesso = 3
            GROUP BY c.idColaborador, c.nome
        """)
        colaboradores = cur.fetchall()
        
        if not colaboradores:
            return []
        
        # Se não encontrou habilidades específicas no projeto, retorna todos colaboradores com 0%
        if not habilidades_match:
            return [{
                'id': c['idColaborador'], 
                'nome': c['nome'], 
                'aderencia': 0.0, 
                'habilidades_comuns': []
            } for c in colaboradores]
            
        # Processar habilidades do projeto (limpar espaços e converter para minúsculas)
        habilidades_projeto_raw = habilidades_match.group(1).split(',')
        habilidades_projeto = [h.strip().lower() for h in habilidades_projeto_raw if h.strip()]
        
        # Criar resultados para TODOS os colaboradores
        resultados = []
        for colaborador in colaboradores:
            # Processar habilidades do colaborador
            habilidades_colab_raw = (colaborador['habilidades'] or '').split(',')
            habilidades_colab = [h.strip().lower() for h in habilidades_colab_raw if h.strip()]
            
            # Encontrar habilidades em comum (comparação exata)
            habilidades_comuns = []
            for habilidade_projeto in habilidades_projeto:
                for habilidade_colab in habilidades_colab:
                    if habilidade_projeto == habilidade_colab:
                        habilidades_comuns.append(habilidade_projeto)
                        break
            
            # Calcular percentual de aderência
            if habilidades_projeto:
                percentual_aderencia = (len(habilidades_comuns) / len(habilidades_projeto)) * 100
            else:
                percentual_aderencia = 0.0
            
            resultados.append({
                'id': colaborador['idColaborador'],
                'nome': colaborador['nome'],
                'aderencia': round(percentual_aderencia, 2),
                'habilidades_comuns': habilidades_comuns
            })
        
        # Ordenar por maior aderência
        resultados.sort(key=lambda x: x['aderencia'], reverse=True)
        return resultados
        
    except Exception as e:
        print(f"ERRO CRÍTICO em calcular_aderencia_projeto: {e}")
        # Em caso de erro, retorna lista vazia para não quebrar a interface
        return []
    finally:
        if cur: 
            cur.close()

# =============================================================================
# ROTAS DE UTILIDADE E DIAGNÓSTICO
# =============================================================================

@app.route('/api/stats')
@login_required
def get_stats():
    try:
        cur = mysql.connection.cursor()
        
        # Estatísticas básicas
        cur.execute("SELECT COUNT(*) as total FROM Demandas")
        total_projetos = cur.fetchone()['total']
        
        cur.execute("SELECT COUNT(*) as total FROM ADM")
        total_usuarios = cur.fetchone()['total']
        
        cur.execute("""
            SELECT s.status, COUNT(*) as count 
            FROM Demandas d 
            JOIN StatusDemanda s ON d.idStatusDemanda = s.idStatusDemanda 
            GROUP BY s.status
        """)
        status_stats = cur.fetchall()
        
        cur.close()
        
        return jsonify({
            'success': True,
            'data': {
                'total_projetos': total_projetos,
                'total_usuarios': total_usuarios,
                'status_stats': status_stats
            }
        })
    
    except Exception as e:
        print(f"Erro em get_stats: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/fix-passwords')
def fix_passwords():
    """Rota temporária para corrigir senhas no banco"""
    try:
        cur = mysql.connection.cursor()
        
        # Atualizar senhas dos usuários
        usuarios = [
            ('admin@ruby.com', generate_password_hash("cah@123")),
            ('joao.silva@ruby.com', "cah@123"),  # Mantém em texto para primeiro login
            ('maria.santos@ruby.com', "cah@123"), # Mantém em texto para primeiro login
        ]
        
        for email, senha in usuarios:
            cur.execute("UPDATE ADM SET senha = %s WHERE email = %s", (senha, email))
        
        mysql.connection.commit()
        cur.close()
        
        return """
        <h1>Senhas corrigidas com sucesso!</h1>
        <p>Credenciais:</p>
        <ul>
            <li><strong>Admin:</strong> admin@ruby.com / cah@123</li>
            <li><strong>Estagiário 1:</strong> joao.silva@ruby.com / cah@123</li>
            <li><strong>Estagiário 2:</strong> maria.santos@ruby.com / cah@123</li>
        </ul>
        <a href='/login'>Fazer Login</a>
        """
        
    except Exception as e:
        return f"<h1>Erro ao corrigir senhas:</h1><p>{e}</p>"

@app.route('/health')
def health_check():
    """Rota para verificar status do sistema (Railway)"""
    try:
        cur = mysql.connection.cursor()
        cur.execute("SELECT 1")
        cur.close()
        
        return jsonify({
            'status': 'healthy',
            'database': 'connected',
            'timestamp': datetime.now().isoformat(),
            'environment': 'railway'
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'database': 'disconnected',
            'error': str(e)
        }), 500

# =============================================================================
# INICIALIZAÇÃO (CORRIGIDA PARA RAILWAY)
# =============================================================================

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 SISTEMA KANBAN RUBY ALIGNMENT - RAILWAY")
    print("=" * 60)
    print("📧 Credenciais para teste:")
    print("   Admin: admin@ruby.com / cah@123")
    print("   Estagiário 1: joao.silva@ruby.com / cah@123")
    print("   Estagiário 2: maria.santos@ruby.com / cah@123")
    print("=" * 60)
    print("🔧 Acesse /fix-passwords se precisar corrigir senhas")
    print("❤️  Acesse https://perfect-creativity-rubya.up.railway.app")
    print("=" * 60)
    
    port = int(os.environ.get('PORT', 5000))

    app.run(host='0.0.0.0', port=port, debug=False)



