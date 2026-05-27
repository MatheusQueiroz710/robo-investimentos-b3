# 1. Usa uma versão leve e oficial do Python como base
FROM python:3.11-slim

# 2. Define a pasta principal lá dentro da máquina virtual
WORKDIR /app

# 3. Copia a nossa lista de bibliotecas para dentro
COPY requirements.txt .

# 4. Instala todas as bibliotecas sem guardar lixo (cache)
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copia o seu código Python para a máquina virtual
COPY app.py .

# 6. Define o fuso horário para o Brasil (para o schedule rodar na hora certa)
ENV TZ=America/Sao_Paulo
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 7. O comando que dá a partida no robô (o -u força os prints a aparecerem no log da nuvem na mesma hora)
CMD ["python", "-u", "app.py"]