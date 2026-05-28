from flask import Flask, render_template, request, redirect, url_for, session, send_file, flash
from datetime import datetime
import sqlite3
import os
from fpdf import FPDF

app = Flask(__name__)
app.secret_key = "chave_secreta_super_segura" # Necessário para o sistema de login/sessão

ARQUIVO_LOGO = "logo.png"

USUARIOS_CADASTRADOS = {
    "motorista1": ("João Silva", "M-12345", "1234"),
    "motorista2": ("Maria Souza", "M-67890", "abcd")
}

def inicializar_banco():
    conn = sqlite3.connect("diario_bordo.db")
    cursor = conn.cursor()
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
            status TEXT DEFAULT 'Em Andamento'
        )
    """)
    conn.commit()
    conn.close()

# --- ROTA: TELA DE LOGIN ---
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form.get("usuario").strip()
        senha = request.form.get("senha").strip()
        
        if usuario in USUARIOS_CADASTRADOS and USUARIOS_CADASTRADOS[usuario][2] == senha:
            session["usuario"] = usuario
            session["nome"] = USUARIOS_CADASTRADOS[usuario][0]
            session["matricula"] = USUARIOS_CADASTRADOS[usuario][1]
            return redirect(url_for("painel"))
        else:
            flash("Usuário ou senha incorretos!", "erro")
            
    return render_template("login.html")

# --- ROTA: LOGOUT ---
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# --- ROTA: PAINEL PRINCIPAL ---
@app.route("/painel", methods=["GET", "POST"])
def painel():
    if "usuario" not in session:
        return redirect(url_for("login"))
        
    conn = sqlite3.connect("diario_bordo.db")
    cursor = conn.cursor()
    
    # Verifica se o motorista logado tem alguma viagem em andamento
    cursor.execute("SELECT id, origem, km_saida, hora_saida, data FROM viagens WHERE motorista = ? AND status = 'Em Andamento'", (session["nome"],))
    viagem_andamento = cursor.fetchone()
    
    if request.method == "POST":
        acao = request.form.get("acao")
        
        if acao == "iniciar":
            origem = request.form.get("origem")
            km_saida = request.form.get("km_saida")
            hora_saida = request.form.get("hora_saida")
            data_atual = datetime.now().strftime("%d/%m/%Y")
            
            cursor.execute("""
                INSERT INTO viagens (motorista, matricula, data, origem, km_saida, hora_saida, status)
                VALUES (?, ?, ?, ?, ?, ?, 'Em Andamento')
            """, (session["nome"], session["matricula"], data_atual, origem, km_saida, hora_saida))
            conn.commit()
            flash("Viagem iniciada com sucesso!", "sucesso")
            return redirect(url_for("painel"))
            
        elif acao == "finalizar":
            viagem_id = request.form.get("viagem_id")
            destino = request.form.get("destino")
            km_chegada = float(request.form.get("km_chegada"))
            hora_chegada = request.form.get("hora_chegada")
            motivo = request.form.get("motivo")
            
            # Pega o km de saída para calcular
            cursor.execute("SELECT km_saida FROM viagens WHERE id = ?", (viagem_id,))
            km_saida = cursor.fetchone()[0]
            
            if km_chegada < km_saida:
                flash("O KM de chegada não pode ser menor que o de saída!", "erro")
            else:
                km_rodados = km_chegada - km_saida
                cursor.execute("""
                    UPDATE viagens 
                    SET destino = ?, km_chegada = ?, hora_chegada = ?, km_rodados = ?, motivo = ?, status = 'Finalizada'
                    WHERE id = ?
                """, (destino, km_chegada, hora_chegada, km_rodados, motivo, viagem_id))
                conn.commit()
                flash("Viagem finalizada com sucesso!", "sucesso")
                return redirect(url_for("painel"))
                
    conn.close()
    return render_template("painel.html", viagem=viagem_andamento)

# --- ROTA: HISTÓRICO ---
@app.route("/historico")
def historico():
    if "usuario" not in session:
        return redirect(url_for("login"))
        
    conn = sqlite3.connect("diario_bordo.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, data, motorista, origem, destino, km_rodados FROM viagens WHERE status = 'Finalizada' ORDER BY id DESC")
    viagens = cursor.fetchall()
    conn.close()
    
    return render_template("historico.html", viagens=viagens)

# --- ROTA: GERAR PDF ANEXADO ---
@app.route("/gerar_pdf/<int:id_viagem>")
def gerar_pdf(id_viagem):
    if "usuario" not in session:
        return redirect(url_for("login"))
        
    conn = sqlite3.connect("diario_bordo.db")
    cursor = conn.cursor()
    cursor.execute("SELECT motorista, matricula, data, origem, destino, km_saida, km_chegada, hora_saida, hora_chegada, km_rodados, motivo FROM viagens WHERE id = ?", (id_viagem,))
    resultado = cursor.fetchone()
    conn.close()
    
    if not resultado:
        return "Viagem não encontrada", 404

    dados = {
        "motorista": resultado[0], "matricula": resultado[1], "data": resultado[2],
        "origem": resultado[3], "destino": resultado[4], "km_saida": resultado[5],
        "km_chegada": resultado[6], "hora_saida": resultado[7], "hora_chegada": resultado[8],
        "km_rodados": resultado[9], "motivo": resultado[10]
    }

    # Lógica de geração do PDF (exatamente como você já tinha)
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
    pdf.cell(0, 8, "1. Identificação do Condutor", ln=True)
    pdf.set_font("Arial", "", 11)
    pdf.cell(0, 6, f"Motorista: {dados['motorista']}", ln=True)
    pdf.cell(0, 6, f"Matrícula: {dados['matricula']}", ln=True)
    pdf.cell(0, 6, f"Data da Viagem: {dados['data']}", ln=True)
    pdf.ln(5)
    
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 8, "2. Rota e Percurso Rodado", ln=True)
    pdf.set_font("Arial", "", 11)
    pdf.cell(0, 6, f"Origem: {dados['origem']}   |   Destino: {dados['destino']}", ln=True)
    pdf.cell(0, 6, f"KM de Saída: {dados['km_saida']} KM  |  Horário de Saída: {dados['hora_saida']}", ln=True)
    pdf.cell(0, 6, f"KM de Chegada: {dados['km_chegada']} KM  |  Horário de Chegada: {dados['hora_chegada']}", ln=True)
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
    
    # O Flask envia o arquivo gerado direto para download no celular/computador do usuário
    return send_file(nome_arquivo, as_attachment=True)

if __name__ == "__main__":
    inicializar_banco()
    app.run(debug=True, host="0.0.0.0") # host="0.0.0.0" permite que celulares na mesma rede acessem