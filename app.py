from flask import Flask, render_template, request, redirect, url_for, session, send_file, flash
from datetime import datetime
import sqlite3
import os
from fpdf import FPDF

app = Flask(__name__)
app.secret_key = "chave_secreta_super_segura"

ARQUIVO_LOGO = "static/logo.png"

USUARIOS_CADASTRADOS = {
    "motorista1": ("João Silva", "M-12345", "1234", "motorista"),
    "motorista2": ("Maria Souza", "M-67890", "abcd", "motorista"),
    "admin1": ("Carlos Gestor", "A-00001", "admin123", "admin")
}

# Lista com todos os itens do check-list para facilitar a automação no código
ITENS_CHECKLIST = [
    "pneus", "combustivel", "arla", "vidros_laterais", "parabrisa", 
    "limpadores", "farol_baixo", "farol_alto", "seta_direita", 
    "seta_esquerda", "pisca_alerta", "carroceria", "parachoque_dianteiro", 
    "parachoque_traseiro", "freio_estacionario", "interior", "cintos"
]

def inicializar_banco():
    conn = sqlite3.connect("diario_bordo.db")
    cursor = conn.cursor()
    
    # Tabela principal de viagens
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS viagens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            motorista TEXT,
            matricula TEXT,
            data TEXT,
            origem TEXT,
            destino TEXT,
            km_saida REAL,
            km_chegada REAL,
            hora_saida TEXT,
            hora_chegada TEXT,
            km_rodados REAL,
            motivo TEXT,
            status TEXT DEFAULT 'Em Andamento',
            placa TEXT,
            frota TEXT,
            lat_saida TEXT,
            lon_saida TEXT,
            lat_chegada TEXT,
            lon_chegada TEXT
        )
    """)
    
    # Nova Tabela para armazenar os Check-lists vinculados à viagem
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS checklists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            viagem_id INTEGER,
            pneus TEXT, combustivel TEXT, arla TEXT, vidros_laterais TEXT, parabrisa TEXT,
            limpadores TEXT, farol_baixo TEXT, farol_alto TEXT, seta_direita TEXT,
            seta_esquerda TEXT, pisca_alerta TEXT, carroceria TEXT, parachoque_dianteiro TEXT,
            parachoque_traseiro TEXT, freio_estacionario TEXT, interior TEXT, cintos TEXT,
            FOREIGN KEY(viagem_id) REFERENCES viagens(id)
        )
    """)
    
    # Migração segura de colunas antigas caso necessário
    novas_colunas = ["lat_saida", "lon_saida", "lat_chegada", "lon_chegada"]
    for col in novas_colunas:
        try: cursor.execute(f"ALTER TABLE viagens ADD COLUMN {col} TEXT")
        except sqlite3.OperationalError: pass
            
    conn.commit()
    conn.close()

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form.get("usuario").strip()
        senha = request.form.get("senha").strip()
        if usuario in USUARIOS_CADASTRADOS and USUARIOS_CADASTRADOS[usuario][2] == senha:
            session["usuario"] = usuario
            session["nome"] = USUARIOS_CADASTRADOS[usuario][0]
            session["matricula"] = USUARIOS_CADASTRADOS[usuario][1]
            session["perfil"] = USUARIOS_CADASTRADOS[usuario][3]
            return redirect(url_for("admin_painel" if session["perfil"] == "admin" else "painel"))
        else:
            flash("Usuário ou senha incorretos!", "erro")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/painel", methods=["GET", "POST"])
def painel():
    if "usuario" not in session or session["perfil"] != "motorista":
        return redirect(url_for("login"))
        
    conn = sqlite3.connect("diario_bordo.db")
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, origem, km_saida, hora_saida, data, placa, frota FROM viagens WHERE motorista = ? AND status = 'Em Andamento'", (session["nome"],))
    viagem_andamento = cursor.fetchone()
    
    if request.method == "POST":
        acao = request.form.get("acao")
        
        if acao == "iniciar":
            origem = request.form.get("origem")
            km_saida = request.form.get("km_saida")
            hora_saida = request.form.get("hora_saida")
            placa = request.form.get("placa").strip().upper()
            frota = request.form.get("frota").strip()
            lat_saida = request.form.get("lat_saida")
            lon_saida = request.form.get("lon_saida")
            data_atual = datetime.now().strftime("%d/%m/%Y")
            
            # 1. Salva a viagem
            cursor.execute("""
                INSERT INTO viagens (motorista, matricula, data, origem, km_saida, hora_saida, placa, frota, lat_saida, lon_saida, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Em Andamento')
            """, (session["nome"], session["matricula"], data_atual, origem, km_saida, hora_saida, placa, frota, lat_saida, lon_saida))
            viagem_id = cursor.lastrowid
            
            # 2. Captura as respostas do check-list (se vier marcado no form é 'OK', se não vier é 'Não Conforme')
            respostas_chk = {item: ("OK" if request.form.get(f"chk_{item}") else "Não Conforme") for item in ITENS_CHECKLIST}
            
            # 3. Salva o check-list no banco
            cursor.execute("""
                INSERT INTO checklists (
                    viagem_id, pneus, combustivel, arla, vidros_laterais, parabrisa,
                    limpadores, farol_baixo, farol_alto, seta_direita, seta_esquerda,
                    pisca_alerta, carroceria, parachoque_dianteiro, parachoque_traseiro,
                    freio_estacionario, interior, cintos
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                viagem_id, respostas_chk["pneus"], respostas_chk["combustivel"], respostas_chk["arla"],
                respostas_chk["vidros_laterais"], respostas_chk["parabrisa"], respostas_chk["limpadores"],
                respostas_chk["farol_baixo"], respostas_chk["farol_alto"], respostas_chk["seta_direita"],
                respostas_chk["seta_esquerda"], respostas_chk["pisca_alerta"], respostas_chk["carroceria"],
                respostas_chk["parachoque_dianteiro"], respostas_chk["parachoque_traseiro"],
                respostas_chk["freio_estacionario"], respostas_chk["interior"], respostas_chk["cintos"]
            ))
            
            conn.commit()
            flash("Check-list registrado e viagem iniciada!", "sucesso")
            return redirect(url_for("painel"))
            
        elif acao == "finalizar":
            viagem_id = request.form.get("viagem_id")
            destino = request.form.get("destino")
            km_chegada = float(request.form.get("km_chegada"))
            hora_chegada = request.form.get("hora_chegada")
            motivo = request.form.get("motivo")
            lat_chegada = request.form.get("lat_chegada")
            lon_chegada = request.form.get("lon_chegada")
            
            cursor.execute("SELECT km_saida FROM viagens WHERE id = ?", (viagem_id,))
            km_saida = cursor.fetchone()[0]
            
            if km_chegada < km_saida:
                flash("O KM de chegada não pode ser menor que o de saída!", "erro")
            else:
                km_rodados = km_chegada - km_saida
                cursor.execute("""
                    UPDATE viagens 
                    SET destino = ?, km_chegada = ?, hora_chegada = ?, km_rodados = ?, motivo = ?, lat_chegada = ?, lon_chegada = ?, status = 'Finalizada'
                    WHERE id = ?
                """, (destino, km_chegada, hora_chegada, km_rodados, motivo, lat_chegada, lon_chegada, viagem_id))
                conn.commit()
                flash("Viagem finalizada com sucesso!", "sucesso")
                return redirect(url_for("painel"))
                
    conn.close()
    return render_template("painel.html", viagem=viagem_andamento)

@app.route("/historico")
def historico():
    if "usuario" not in session or session["perfil"] != "motorista":
        return redirect(url_for("login"))
    conn = sqlite3.connect("diario_bordo.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, data, motorista, origem, destino, km_rodados FROM viagens WHERE motorista = ? AND status = 'Finalizada' ORDER BY id DESC", (session["nome"],))
    viagens = cursor.fetchall()
    conn.close()
    return render_template("historico.html", viagens=viagens)

@app.route("/admin/painel")
def admin_painel():
    if "usuario" not in session or session["perfil"] != "admin":
        return redirect(url_for("login"))
        
    conn = sqlite3.connect("diario_bordo.db")
    cursor = conn.cursor()
    
    cursor.execute("SELECT data, motorista, origem, km_saida, hora_saida, placa, frota, lat_saida, lon_saida, id FROM viagens WHERE status = 'Em Andamento' ORDER BY id DESC")
    em_andamento = cursor.fetchall()
    
    cursor.execute("SELECT id, data, motorista, origem, destino, km_rodados, placa, frota, lat_saida, lon_saida, lat_chegada, lon_chegada FROM viagens WHERE status = 'Finalizada' ORDER BY id DESC")
    finalizadas = cursor.fetchall()
    
    conn.close()
    return render_template("admin.html", em_andamento=em_andamento, finalizadas=finalizadas)

@app.route("/admin/checklist/<int:viagem_id>")
def visualizar_checklist(viagem_id):
    if "usuario" not in session or session["perfil"] != "admin":
        return redirect(url_for("login"))
        
    conn = sqlite3.connect("diario_bordo.db")
    cursor = conn.cursor()
    
    # Puxa informações da viagem + do checklist de forma cruzada
    cursor.execute("""
        SELECT v.motorista, v.placa, v.frota, v.data,
               c.pneus, c.combustivel, c.arla, c.vidros_laterais, c.parabrisa,
               c.limpadores, c.farol_baixo, c.farol_alto, c.seta_direita,
               c.seta_esquerda, c.pisca_alerta, c.carroceria, c.parachoque_dianteiro,
               c.parachoque_traseiro, c.freio_estacionario, c.interior, c.cintos
        FROM checklists c
        JOIN viagens v ON c.viagem_id = v.id
        WHERE c.viagem_id = ?
    """, (viagem_id,))
    chk = cursor.fetchone()
    conn.close()
    
    if not chk:
        return "Check-list não localizado para esta viagem.", 404
        
    # Organiza em um dicionário estruturado para enviar ao template dinâmico
    dados_checklist = {
        "motorista": chk[0], "placa": chk[1], "frota": chk[2], "data": chk[3],
        "itens": {
            "Pneus / Calibragem": chk[4], "Nível de Combustível": chk[5], "Fluido Arla 32": chk[6],
            "Vidros Laterais": chk[7], "Para-brisa": chk[8], "Limpadores de Para-brisa": chk[9],
            "Farol Baixo": chk[10], "Farol Alto": chk[11], "Seta Direita": chk[12],
            "Seta Esquerda": chk[13], "Pisca Alerta": chk[14], "Estrutura da Carroceria": chk[15],
            "Para-choque Dianteiro": chk[16], "Para-choque Traseiro": chk[17],
            "Freio de Estacionamento": chk[18], "Higienização Interior": chk[19], "Cintos de Segurança": chk[20]
        }
    }
    return render_template("checklist_ver.html", chk=dados_checklist)

@app.route("/gerar_pdf/<int:id_viagem>")
def gerar_pdf(id_viagem):
    if "usuario" not in session:
        return redirect(url_for("login"))
        
    conn = sqlite3.connect("diario_bordo.db")
    cursor = conn.cursor()
    cursor.execute("SELECT motorista, matricula, data, origem, destino, km_saida, km_chegada, hora_saida, hora_chegada, km_rodados, motivo, placa, frota, lat_saida, lon_saida, lat_chegada, lon_chegada FROM viagens WHERE id = ?", (id_viagem,))
    resultado = cursor.fetchone()
    conn.close()
    
    if not resultado:
        return "Viagem não encontrada", 404

    dados = {
        "motorista": resultado[0], "matricula": resultado[1], "data": resultado[2],
        "origem": resultado[3], "destino": resultado[4], "km_saida": resultado[5],
        "km_chegada": float(resultado[6]) if resultado[6] else 0.0, "hora_saida": resultado[7], "hora_chegada": resultado[8],
        "km_rodados": resultado[9], "motivo": resultado[10],
        "placa": resultado[11] if resultado[11] else "Não Informado",
        "frota": resultado[12] if resultado[12] else "Não Informado",
        "coordenadas": f"Saída: ({resultado[13]}, {resultado[14]}) | Chegada: ({resultado[15]}, {resultado[16]})" if resultado[13] else "Não registradas"
    }

    pdf = FPDF()
    pdf.add_page()
    pdf.set_fill_color(33, 150, 243) 
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", "B", 14)
    
    if os.path.exists(ARQUIVO_LOGO):
        pdf.cell(130, 15, "RELATÓRIO DE VIAGEM / DIÁRIO DE BORDO", ln=False, align="C", fill=True)
        pdf.image(ARQUIVO_LOGO, x=150, y=10, w=50)
        pdf.ln(20)
    else:
        pdf.cell(0, 15, "RELATÓRIO DE VIAGEM / DIÁRIO DE BORDO", ln=True, align="C", fill=True)
        pdf.ln(10)
        
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 8, "1. Identificação do Condutor e Veículo", ln=True)
    pdf.set_font("Arial", "", 11)
    pdf.cell(0, 6, f"Motorista: {dados['motorista']}  |  Matrícula: {dados['matricula']}", ln=True)
    pdf.cell(0, 6, f"Veículo (Placa): {dados['placa']}  |  Nº da Frota: {dados['frota']}", ln=True)
    pdf.cell(0, 6, f"Data da Viagem: {dados['data']}", ln=True)
    pdf.ln(5)
    
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 8, "2. Rota e Percurso Rodado", ln=True)
    pdf.set_font("Arial", "", 11)
    pdf.cell(0, 6, f"Origem: {dados['origem']}   |   Destino: {dados['destino']}", ln=True)
    pdf.cell(0, 6, f"KM de Saída: {dados['km_saida']} KM  |  Horário de Saída: {dados['hora_saida']}", ln=True)
    pdf.cell(0, 6, f"KM de Chegada: {dados['km_chegada']} KM  |  Horário de Chegada: {dados['hora_chegada']}", ln=True)
    pdf.cell(0, 6, f"GPS Coordenadas: {dados['coordenadas']}", ln=True)
    pdf.set_font("Arial", "B", 11)
    pdf.cell(0, 8, f"Total Quilometragem Rodada: {dados['km_rodados']} KM", ln=True)
    pdf.ln(5)
    
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 8, "3. Justificativa / Motivo da Viagem", ln=True)
    pdf.set_font("Arial", "", 11)
    pdf.multi_cell(0, 6, dados['motivo'])
    pdf.ln(25)
    
    pdf.cell(0, 0, "", border="T", ln=True, align="C")
    pdf.set_font("Arial", "I", 10)
    pdf.cell(0, 8, f"Assinatura do Motorista ({dados['motorista']})", ln=True, align="C")
    
    nome_arquivo = f"viagem_id{id_viagem}.pdf"
    pdf.output(nome_arquivo)
    
    return send_file(nome_arquivo, as_attachment=True)

if __name__ == "__main__":
    inicializar_banco()
    app.run(debug=True, host="0.0.0.0")