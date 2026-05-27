import yfinance as yf
from google import genai
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from datetime import datetime
from dotenv import load_dotenv
import gspread
from google.oauth2.service_account import Credentials
import json

# Carrega as variáveis de ambiente de forma segura
load_dotenv()

# Configuração da IA (Gemini Client)
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# ---------------- CONFIGURAÇÃO DA CARTEIRA ----------------
# Altere os valores abaixo para os seus preços-alvo reais quando quiser rodar para valer
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
#    if hora < 10 or hora >= 18:
#        return False
        
    return True

def consultar_gemini_relatorio(lista_ativos_atingidos):
    """Pede para a IA analisar todos os ativos juntos e o cenário geral da B3"""
    texto_ativos = "\n".join([f"- {item['ativo']}: R$ {item['preco_atual']:.2f}" for item in lista_ativos_atingidos])
    
    prompt = f"""
Atue como um analista financeiro sênior. As seguintes ações da bolsa brasileira atingiram meus alvos de compra hoje:
{texto_ativos}

Por favor, crie um relatório curto e direto estruturado in duas partes:
1. Panorama Geral: Como está o índice Ibovespa hoje e o clima geral do mercado financeiro mundial/brasileiro.
2. Análise dos Ativos: Resuma os principais motivos, notícias recentes ou contexto de mercado que justificam a oscilação específica dessas empresas listadas acima.
"""
    try:
        resposta = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        return resposta.text
    except Exception as e:
        return f"Erro ao consultar a IA: {e}"

def enviar_email_consolidado(lista_ativos_atingidos, analise_mercado):
    """Envia um único e-mail com a lista de ativos e a análise da IA"""
    remetente = os.getenv("EMAIL_REMETENTE")
    senha = os.getenv("SENHA_APP_EMAIL")
    destino = os.getenv("EMAIL_DESTINO")
    
    assunto = f"⚠️ RELATÓRIO DE MERCADO: {len(lista_ativos_atingidos)} oportunidade(s) na B3!"
    
    texto_lista = ""
    for item in lista_ativos_atingidos:
        texto_lista += f"🎯 {item['ativo']} | Atual: R$ {item['preco_atual']:.2f} (Alvo: R$ {item['preco_alvo']:.2f})\n"
    
    corpo = f"""
Olá! Aqui está o seu relatório consolidado de investimentos deste ciclo.
    
--- ATIVOS QUE ATINGIRAM O ALVO ---
{texto_lista}
    
--- ANÁLISE DE MERCADO (GEMINI IA) ---
{analise_mercado}
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
        print(f"✅ Relatório consolidado enviado com sucesso!")
    except Exception as e:
        print(f"❌ Erro ao enviar e-mail. Verifique a Senha de App no cofre. Erro: {e}")

def atualizar_planilha(lista_ativos_atingidos):
    """Acessa o Google Sheets e escreve os alertas na aba Histórico de Alertas"""
    try:
        print("📊 Conectando ao Google Sheets...")
        credenciais_json = json.loads(os.getenv("GOOGLE_CREDENTIALS"))
        
        escopos = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        
        credenciais = Credentials.from_service_account_info(credenciais_json, scopes=escopos)
        cliente_sheets = gspread.authorize(credenciais)
        
        # Abre a planilha e direciona os dados para a nova aba de histórico
        planilha = cliente_sheets.open("Planejamento de investimento").worksheet("Histórico de Alertas")
        
        for item in lista_ativos_atingidos:
            nova_linha = [
                datetime.now().strftime('%d/%m/%Y %H:%M'),
                item['ativo'],
                f"R$ {item['preco_atual']:.2f}",
                f"R$ {item['preco_alvo']:.2f}"
            ]
            planilha.append_row(nova_linha)
            
        print("✅ Dados escritos no Histórico de Alertas com sucesso!")
        
    except Exception as e:
        print(f"❌ Erro ao atualizar o Google Sheets: {e}")

def executar_pipeline():
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Iniciando verificação de mercado...")
    
    if not mercado_aberto():
        print("Mercado fechado. O script rodou, mas a B3 está inativa. Aguardando próximo ciclo.")
        return

    ativos_atingidos = [] 

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
                ativos_atingidos.append({
                    "ativo": ativo,
                    "preco_atual": preco_atual,
                    "preco_alvo": preco_alvo
                })
                
        except Exception as e:
            print(f"Erro ao processar o ativo {ativo}: {e}")

    if ativos_atingidos:
        print(f"🚨 {len(ativos_atingidos)} alvo(s) atingido(s)! Gerando relatório e atualizando planilha...")
        
        # Insere os dados na aba correta de Histórico
        atualizar_planilha(ativos_atingidos)
        
        # Gera a análise da IA e envia por e-mail
        analise = consultar_gemini_relatorio(ativos_atingidos)
        enviar_email_consolidado(ativos_atingidos, analise)
    else:
        print("Tranquilidade. Nenhum ativo atingiu o preço alvo neste ciclo.")

# =========================================================
# GATILHO PRINCIPAL (Acionado pelo GitHub Actions)
# =========================================================
if __name__ == "__main__":
    print("🤖 Robô acionado pela Nuvem.")
    executar_pipeline()
