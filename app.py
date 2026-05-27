import yfinance as yf
from google import genai
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from datetime import datetime
from dotenv import load_dotenv

# Carrega as variáveis de ambiente de forma segura
load_dotenv()

# Configuração da IA (Gemini Client)
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# ---------------- CONFIGURAÇÃO DA CARTEIRA ----------------
CARTEIRA_MONITORAMENTO = [
    ("PETR4.SA", 100.00), 
    ("VALE3.SA", 150.00)
]
# ----------------------------------------------------------

def mercado_aberto():
    """Verifica se é dia útil e se a B3 está operando (10h às 17h)"""
    agora = datetime.now()
    dia_semana = agora.weekday() 
    hora = agora.hour
    
    # Travas de segurança para não rodar de madrugada/fds
    if dia_semana >= 5:
        return False
    #if hora < 10 or hora >= 18:
       # return False
        
    return True

def consultar_gemini(ativo, preco):
    prompt = f"A ação {ativo} está custando atualmente R$ {preco:.2f} e atingiu um preço baixo. Resuma em um parágrafo curto e direto em português as principais notícias recentes ou o contexto de mercado que justificam a oscilação dessa empresa hoje."
    try:
        resposta = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        return resposta.text
    except Exception as e:
        return f"Erro ao consultar a IA: {e}"

def enviar_email(ativo, preco_atual, preco_alvo, analise):
    remetente = os.getenv("EMAIL_REMETENTE")
    senha = os.getenv("SENHA_APP_EMAIL")
    destino = os.getenv("EMAIL_DESTINO")
    
    assunto = f"⚠️ OPORTUNIDADE B3: {ativo} atingiu o alvo!"
    
    corpo = f"""
Alerta de Oportunidade de Investimento
    
Ativo: {ativo}
Preço Alvo Estipulado: R$ {preco_alvo:.2f}
Preço Atual de Mercado: R$ {preco_atual:.2f}
    
--- Contexto da IA (Gemini) ---
{analise}
"""
    msg = MIMEMultipart()
    msg['From'] = remetente
    msg['To'] = destino
    msg['Subject'] = assunto
    msg.attach(MIMEText(corpo, 'plain', 'utf-8'))
    
    try:
        servidor = smtplib.SMTP('smtp.gmail.com', 587)
        servidor.starttls()
        servidor.login(remetente, senha)
        servidor.sendmail(remetente, destino, msg.as_string())
        servidor.quit()
        print(f"✅ E-mail de alerta enviado com sucesso para {ativo}.")
    except Exception as e:
        print(f"❌ Erro ao enviar e-mail. Verifique a Senha de App no cofre. Erro: {e}")

def executar_pipeline():
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Iniciando verificação de mercado...")
    
    if not mercado_aberto():
        print("Mercado fechado. O Cron Job da nuvem rodou, mas a B3 está inativa. Aguardando próximo ciclo.")
        return

    for ativo, preco_alvo in CARTEIRA_MONITORAMENTO:
        try:
            ticker = yf.Ticker(ativo)
            dados_hoje = ticker.history(period="1d")
            
            if dados_hoje.empty:
                print(f"Sem dados para {ativo} no momento.")
                continue
                
            preco_atual = dados_hoje['Close'].iloc[0]
            print(f"Analisando {ativo}: Atual R$ {preco_atual:.2f} | Alvo R$ {preco_alvo:.2f}")
            
            if preco_atual <= preco_alvo:
                print(f"🚨 Alvo atingido para {ativo}! Consultando a IA...")
                analise = consultar_gemini(ativo, preco_atual)
                enviar_email(ativo, preco_atual, preco_alvo, analise)
                
        except Exception as e:
            print(f"Erro ao processar o ativo {ativo}: {e}")

# =========================================================
# GATILHO PRINCIPAL (Acionado pelo servidor do GitHub)
# =========================================================
if __name__ == "__main__":
    print("🤖 Robô acionado pela Nuvem.")
    executar_pipeline()
