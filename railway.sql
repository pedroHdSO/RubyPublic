USE railway;

-- Tabela de Status do Colaborador
CREATE TABLE IF NOT EXISTS StatusColaborador (
    idStatusColaborador INT AUTO_INCREMENT PRIMARY KEY,
    status VARCHAR(15) NOT NULL UNIQUE -- 'ativo', 'inativo'
);

-- Tabela de Departamentos
CREATE TABLE IF NOT EXISTS Departamento (
    idDepartamento INT AUTO_INCREMENT PRIMARY KEY,
    nome VARCHAR(40) NOT NULL UNIQUE,
    descricao TEXT
);

-- Tabela de Cargos
CREATE TABLE IF NOT EXISTS Cargo (
    idCargo INT AUTO_INCREMENT PRIMARY KEY,
    nome VARCHAR(20) NOT NULL UNIQUE,
    descricao TEXT
);

-- Tabela de Colaboradores
CREATE TABLE IF NOT EXISTS Colaborador (
    idColaborador INT AUTO_INCREMENT PRIMARY KEY,
    nome VARCHAR(40) NOT NULL,
    email VARCHAR(35) NOT NULL UNIQUE,
    telefone VARCHAR(15),
    dataAdmissao DATE NOT NULL,
    idCargo INT NOT NULL,
    idDepartamento INT NOT NULL,
    idStatusColaborador INT NOT NULL,
    
    CONSTRAINT fk_Colaborador_Cargo
        FOREIGN KEY (idCargo) REFERENCES Cargo(idCargo)
        ON DELETE RESTRICT
        ON UPDATE CASCADE,
    
    CONSTRAINT fk_Colaborador_Departamento
        FOREIGN KEY (idDepartamento) REFERENCES Departamento(idDepartamento)
        ON DELETE RESTRICT
        ON UPDATE CASCADE,
    
    CONSTRAINT fk_Colaborador_Status
        FOREIGN KEY (idStatusColaborador) REFERENCES StatusColaborador(idStatusColaborador)
        ON DELETE RESTRICT
        ON UPDATE CASCADE
);

-- Tabela de Hard Skills (Competências)
CREATE TABLE IF NOT EXISTS HardSkill (
    idHardSkill INT AUTO_INCREMENT PRIMARY KEY,
    idColaborador INT NOT NULL,
    habilidade VARCHAR(100) NOT NULL,
    
    CONSTRAINT fk_HardSkill_Colaborador
        FOREIGN KEY (idColaborador) REFERENCES Colaborador(idColaborador)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);

-- Tabela de Solicitantes
CREATE TABLE IF NOT EXISTS Solicitante (
    idSolicitante INT AUTO_INCREMENT PRIMARY KEY,
    nome VARCHAR(45) NOT NULL,
    email VARCHAR(30) NOT NULL UNIQUE,
    telefone VARCHAR(15),
    cpf VARCHAR(14) NOT NULL UNIQUE,
    dataCadastro DATE NOT NULL,
    senha VARCHAR(255) NOT NULL
);

-- Tabela de Status das Demandas (ADICIONADA para compatibilidade com KANBAN)
CREATE TABLE IF NOT EXISTS StatusDemanda (
    idStatusDemanda INT AUTO_INCREMENT PRIMARY KEY,
    status VARCHAR(20) NOT NULL UNIQUE -- 'Aberta', 'Em andamento', 'Em monitoramento', 'Concluída', 'Cancelada'
);

-- Tabela de Prioridades das Demandas (ADICIONADA para compatibilidade com KANBAN)
CREATE TABLE IF NOT EXISTS PrioridadeDemanda (
    idPrioridadeDemanda INT AUTO_INCREMENT PRIMARY KEY,
    prioridade VARCHAR(10) NOT NULL UNIQUE -- 'Baixa', 'Média', 'Alta', 'Urgente'
);

-- Tabela de Demandas/Projetos (ATUALIZADA com campos do KANBAN)
CREATE TABLE IF NOT EXISTS Demandas (
    idDemandas INT AUTO_INCREMENT PRIMARY KEY,
    titulo VARCHAR(100) NOT NULL,
    descricao TEXT NOT NULL,
    dataAbertura DATETIME NOT NULL,
    dataLimite DATE,
    dataConclusao DATETIME,
    idSolicitante INT NOT NULL,
    idColaborador INT NOT NULL,
    idStatusDemanda INT NOT NULL,
    idPrioridadeDemanda INT NOT NULL,
    
    -- CAMPOS ADICIONAIS DO SISTEMA KANBAN
    supervisor_responsavel VARCHAR(100),
    supervisor_corresponsavel VARCHAR(100),
    estagiario_responsavel VARCHAR(100),
    estagiario_corresponsavel VARCHAR(100),
    inicio_projeto DATE,
    previsao_termino DATE,
    reuniao_requisitos VARCHAR(20) DEFAULT 'NÃO REALIZADO',
    coleta_preparacao_dados VARCHAR(20) DEFAULT 'NÃO REALIZADO',
    criacao_relatorio_dashboard VARCHAR(20) DEFAULT 'NÃO REALIZADO',
    validacao_refinamento VARCHAR(20) DEFAULT 'NÃO REALIZADO',
    documentacao VARCHAR(20) DEFAULT 'NÃO REALIZADO',
    periodo VARCHAR(100),
    objetivo TEXT,
    observacao TEXT,
    
    CONSTRAINT fk_Demandas_Solicitante
        FOREIGN KEY (idSolicitante) REFERENCES Solicitante(idSolicitante)
        ON DELETE CASCADE
        ON UPDATE CASCADE,
    
    CONSTRAINT fk_Demandas_Colaborador
        FOREIGN KEY (idColaborador) REFERENCES Colaborador(idColaborador)
        ON DELETE CASCADE
        ON UPDATE CASCADE,
    
    CONSTRAINT fk_Demandas_Status
        FOREIGN KEY (idStatusDemanda) REFERENCES StatusDemanda(idStatusDemanda)
        ON DELETE RESTRICT
        ON UPDATE CASCADE,
    
    CONSTRAINT fk_Demandas_Prioridade
        FOREIGN KEY (idPrioridadeDemanda) REFERENCES PrioridadeDemanda(idPrioridadeDemanda)
        ON DELETE RESTRICT
        ON UPDATE CASCADE
);

-- Tabela de Níveis de Acesso
CREATE TABLE IF NOT EXISTS NivelAcesso (
    idNivelAcesso INT AUTO_INCREMENT PRIMARY KEY,
    nivel VARCHAR(15) NOT NULL UNIQUE -- 'super admin', 'admin comum', 'usuário'
);

-- Tabela de Administradores (ATUALIZADA para funcionar como tabela de usuários do sistema)
CREATE TABLE IF NOT EXISTS ADM (
    idADM INT AUTO_INCREMENT PRIMARY KEY,
    nome VARCHAR(60) NOT NULL,
    email VARCHAR(100) NOT NULL UNIQUE,
    senha VARCHAR(255) NOT NULL,
    dataCadastro DATETIME NOT NULL,
    idColaborador INT NOT NULL,
    idNivelAcesso INT NOT NULL,
    status VARCHAR(10) DEFAULT 'OK', -- 'OK', 'TEMP' (para primeiro login)
    
    CONSTRAINT fk_ADM_Colaborador
        FOREIGN KEY (idColaborador) REFERENCES Colaborador(idColaborador)
        ON DELETE CASCADE
        ON UPDATE CASCADE,
    
    CONSTRAINT fk_ADM_NivelAcesso
        FOREIGN KEY (idNivelAcesso) REFERENCES NivelAcesso(idNivelAcesso)
        ON DELETE RESTRICT
        ON UPDATE CASCADE
);

-- Tabela de Logs do Sistema (NOVA TABELA para rastreamento de atividades)
CREATE TABLE IF NOT EXISTS Logs (
    idLog INT AUTO_INCREMENT PRIMARY KEY,
    timestamp DATETIME NOT NULL,
    usuario VARCHAR(60) NOT NULL,
    acao VARCHAR(50) NOT NULL,
    detalhes TEXT
);

-- Índices para melhor performance
CREATE INDEX idx_demandas_status ON Demandas(idStatusDemanda);
CREATE INDEX idx_demandas_prioridade ON Demandas(idPrioridadeDemanda);
CREATE INDEX idx_demandas_data ON Demandas(dataAbertura);
CREATE INDEX idx_adm_email ON ADM(email);
CREATE INDEX idx_logs_timestamp ON Logs(timestamp);