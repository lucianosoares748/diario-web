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

ITENS_CHECKLIST = [
    "pneus", "combustivel", "arla", "vidros_laterais", "parabrisa", 
    "limpadores", "farol_baixo", "farol_alto", "seta_direita", 
    "seta_esquerda", "pisca_alerta", "carroceria", "parachoque_dianteiro", 
    "parachoque_traseiro", "freio_estacionario", "interior", "cintos"
]

def inicializar_banco():
    conn = sqlite3.connect("diario_bordo.db")
    cursor = conn.cursor()
    
    # Tabela de viagens
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
            lat_saida TEXT, lon_saida TEXT,
            lat_chegada TEXT, lon_chegada TEXT
        )
    """)
    
    # Tabela de checklists
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
    
    # Tabela de Veículos da Frota (15 Ônibus)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS veiculos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            frota TEXT UNIQUE,
            placa TEXT,
            status TEXT DEFAULT 'Disponível',
            obs_manutencao TEXT
        )
    """)
    
    # Inserir os 15 ônibus padrão com numeração de frotas e placas Mercosul aleatórias
    cursor.execute("SELECT COUNT(*) FROM veiculos")
    if cursor.fetchone()[0] == 0:
        onibus_iniciais = [
            ("F-01", "ABC1D23"),
            ("F-02", "XYZ9H87"),
            ("F-03", "KGB5M44"),
            ("F-04", "OPX2T11"),
            ("F-05", "BRS7K22"),
            ("F-06", "MTR4J89"),
            ("F-07", "QWE3F45"),
            ("F-08", "PLM9N12"),
            ("F-09", "OKI8B77"),
            ("F-10", "ZXC6V55"),
            ("F-11", "JHG2F11"),
            ("F-12", "REW5T99"),
            ("F-13", "VBN8M33"),
            ("F-14", "HJK4L22"),
            ("F-15", "POI7U11")
        ]
        cursor.executemany("INSERT INTO veiculos (frota, placa) VALUES (?, ?)", onibus_iniciais)
    
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
    
    # Busca apenas os ônibus disponíveis no pátio para o motorista poder escolher
    cursor.execute("SELECT frota, placa FROM veiculos WHERE status = 'Disponível' ORDER BY frota")
    veiculos_disponiveis = cursor.fetchall()
    
    if request.method == "POST":
        acao = request.form.get("acao")
        
        if acao == "iniciar":
            origem = request.form.get("origem")
            km_saida = request.form.get("km_saida")
            hora_saida = request.form.get("hora_saida")
            
            frota = request.form.get("frota")
            cursor.execute("SELECT placa FROM veiculos WHERE frota = ?", (frota,))
            resultado_placa = cursor.fetchone()
            placa = resultado_placa[0] if resultado_placa else "Sem Placa"
            
            lat_saida = request.form.get("lat_saida")
            lon_saida = request.form.get("lon_saida")
            data_atual = datetime.now().strftime("%d/%m/%Y")
            
            # Verifica se o veículo ainda está disponível
            cursor.execute("SELECT status FROM veiculos WHERE frota = ?", (frota,))
            status_atual = cursor.fetchone()[0]
            if status_atual != "Disponível":
                flash("Este veículo acabou de ser pego ou entrou em manutenção!", "erro")
                conn.close()
                return redirect(url_for("painel"))

            # 1. Salva a viagem
            cursor.execute("""
                INSERT INTO viagens (motorista, matricula, data, origem, km_saida, hora_saida, placa, frota, lat_saida, lon_saida, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Em Andamento')
            """, (session["nome"], session["matricula"], data_atual, origem, km_saida, hora_saida, placa, frota, lat_saida, lon_saida))
            viagem_id = cursor.lastrowid
            
            # 2. Atualiza o status do veículo para 'Em Trajeto'
            cursor.execute("UPDATE veiculos SET status = 'Em Trajeto' WHERE frota = ?", (frota,))
            
            # 3. Salva o checklist
            respostas_chk = {item: ("OK" if request.form.get(f"chk_{item}") else "Não Conforme") for item in ITENS_CHECKLIST}
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
            conn.close()
            return redirect(url_for("painel"))
            
        elif acao == "finalizar":
            viagem_id = request.form.get("viagem_id")
            destino = request.form.get("destino")
            km_chegada = float(request.form.get("km_chegada"))
            hora_chegada = request.form.get("hora_chegada")
            motivo = request.form.get("motivo")
            lat_chegada = request.form.get("lat_chegada")
            lon_chegada = request.form.get("lon_chegada")
            
            cursor.execute("SELECT km_saida, frota FROM viagens WHERE id = ?", (viagem_id,))
            viagem_dados = cursor.fetchone()
            km_saida = viagem_dados[0]
            frota_veiculo = viagem_dados[1]
            
            if km_chegada < km_saida:
                flash("O KM de chegada não pode ser menor que o de saída!", "erro")
            else:
                km_rodados = km_chegada - km_saida
                # Finaliza a viagem
                cursor.execute("""
                    UPDATE viagens 
                    SET destino = ?, km_chegada = ?, hora_chegada = ?, km_rodados = ?, motivo = ?, lat_chegada = ?, lon_chegada = ?, status = 'Finalizada'
                    WHERE id = ?
                """, (destino, km_chegada, hora_chegada, km_rodados, motivo, lat_chegada, lon_chegada, viagem_id))
                
                # Devolve o veículo para o status 'Disponível'
                cursor.execute("UPDATE veiculos SET status = 'Disponível' WHERE frota = ?", (frota_veiculo,))
                
                conn.commit()
                flash("Viagem finalizada! Ônibus disponível no pátio.", "sucesso")
                conn.close()
                return redirect(url_for("painel"))
                
    conn.close()
    return render_template("painel.html", viagem=viagem_andamento, veiculos=veiculos_disponiveis)

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
    
    # Carrega os 15 veículos com motorista/destino da viagem atual ativa se houver
    cursor.execute("""
        SELECT v.frota, v.placa, v.status, v.obs_manutencao, vi.motorista, vi.destino, vi.id
        FROM veiculos v
        LEFT JOIN viagens vi ON v.frota = vi.frota AND vi.status = 'Em Andamento'
        ORDER BY v.frota
    """)
    frota_dashboard = cursor.fetchall()
    
    conn.close()
    return render_template("admin.html", em_andamento=em_andamento, finalizadas=finalizadas, frota=frota_dashboard)

@app.route("/admin/manutencao/iniciar", methods=["POST"])
def enviar_manutencao():
    if "usuario" not in session or session["perfil"] != "admin": return redirect(url_for("login"))
    frota = request.form.get("frota")
    motivo = request.form.get("motivo", "Reparo geral")
    
    conn = sqlite3.connect("diario_bordo.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE veiculos SET status = 'Manutenção', obs_manutencao = ? WHERE frota = ?", (motivo, frota))
    conn.commit()
    conn.close()
    flash(f"Veículo {frota} enviado para a oficina.", "sucesso")
    return redirect(url_for("admin_painel"))

@app.route("/admin/manutencao/liberar/<frota>")
def liberar_manutencao(frota):
    if "usuario" not in session or session["perfil"] != "admin": return redirect(url_for("login"))
    
    conn = sqlite3.connect("diario_bordo.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE veiculos SET status = 'Disponível', obs_manutencao = NULL WHERE frota = ?", (frota,))
    conn.commit()
    conn.close()
    flash(f"Veículo {frota} liberado de volta para o pátio!", "sucesso")
    return redirect(url_for("admin_painel"))

@app.route("/admin/checklist/<int:viagem_id>")
def visualizar_checklist(viagem_id):
    if "usuario" not in session or session["perfil"] != "admin": return redirect(url_for("login"))
    conn = sqlite3.connect("diario_bordo.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT v.motorista, v.placa, v.frota, v.data,
               c.pneus, c.combustivel, c.arla, c.vidros_laterais, c.parabrisa,
               c.limpadores, c.farol_baixo, c.farol_alto, c.seta_direita,
               c.seta_esquerda, c.pisca_alerta, c.carroceria, c.parachoque_dianteiro,
               c.parachoque_traseiro, c.freio_estacionario, c.interior, c.cintos
        FROM checklists c JOIN viagens v ON c.viagem_id = v.id WHERE c.viagem_id = ?
    """, (viagem_id,))
    chk = cursor.fetchone()
    conn.close()
    if not chk: return "Check-list não localizado.", 404
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
    if "usuario" not in session: return redirect(url_for("login"))
    conn = sqlite3.connect("diario_bordo.db")
    cursor = conn.cursor()
    cursor.execute("SELECT motorista, matricula, data, origem, destino, km_saida, km_chegada, hora_saida, hora_chegada, km_rodados, motivo, placa, frota, lat_saida, lon_saida, lat_chegada, lon_chegada FROM viagens WHERE id = ?", (id_viagem,))
    resultado = snapshot = cursor.fetchone()
    conn.close()
    if not resultado: return "Viagem não encontrada", 404

    dados = {
        "motorista": resultado[0], "matricula": resultado[1], "data": resultado[2],
        "origem": resultado[3], "destino": resultado[4], "km_saida": resultado[5],
        "km_chegada": float(resultado[6]) if resultado[6] else 0.0, "hora_saida": resultado[7], "hora_chegada": resultado[8],
        "km_rodados": resultado[9], "motivo": resultado[10], "placa": resultado[11], "frota": resultado[12],
        "coordenadas": f"Saída: ({resultado[13]}, {resultado[14]}) | Chegada: ({resultado[15]}, {resultado[16]})" if resultado[13] else "Não registradas"
    }

    pdf = FPDF()
    pdf.add_page()
    pdf.set_fill_color(33, 150, 243) 
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 15, "RELATÓRIO DE VIAGEM / DIÁRIO DE BORDO", ln=True, align="C", fill=True)
    pdf.ln(10)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 8, "1. Identificação do Condutor e Veículo", ln=True)
    pdf.set_font("Arial", "", 11)
    pdf.cell(0, 6, f"Motorista: {dados['motorista']} | Matrícula: {dados['matricula']}", ln=True)
    pdf.cell(0, 6, f"Veículo (Placa): {dados['placa']} | Nº da Frota: {dados['frota']}", ln=True)
    pdf.ln(5)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 8, "2. Percurso", ln=True)
    pdf.set_font("Arial", "", 11)
    pdf.cell(0, 6, f"Origem: {dados['origem']} -> Destino: {dados['destino']}", ln=True)
    pdf.cell(0, 8, f"Total Rodado: {dados['km_rodados']} KM", ln=True)
    
    nome_arquivo = f"viagem_id{id_viagem}.pdf"
    pdf.output(nome_arquivo)
    return send_file(nome_arquivo, as_attachment=True)

if __name__ == "__main__":
    inicializar_banco()
    app.run(debug=True, host="0.0.0.0")