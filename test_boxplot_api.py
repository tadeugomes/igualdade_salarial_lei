import requests

# Testando o envio de um arquivo para processamento
url = "http://localhost:8000/process"  # Local testing URL

# Preparando os dados do formulário
files = {
    'file': ('sample_data.csv', open('sample_data.csv', 'rb'), 'text/csv')
}

data = {
    'company_name': 'Empresa Teste Boxplot',
    'k_min': '5',
    'primary_color': '#0F6CBD',
    'accent_color': '#585858',
    'generate_docx': 'false'
}

# Enviando a requisição POST
try:
    response = requests.post(url, files=files, data=data, timeout=30)
    
    # Verificando a resposta
    print(f"Status Code: {response.status_code}")
    print(f"Headers: {response.headers}")
    
    # Salvando o conteúdo da resposta em um arquivo
    if response.status_code == 200:
        with open('response_output_boxplot.zip', 'wb') as f:
            f.write(response.content)
        print("Response saved to response_output_boxplot.zip")
    else:
        print(f"Response text: {response.text[:500]}...")  # Mostrando apenas os primeiros 500 caracteres
except requests.exceptions.RequestException as e:
    print(f"Request failed: {e}")
except Exception as e:
    print(f"An error occurred: {e}")