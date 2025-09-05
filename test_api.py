import requests

# Testando o envio de um arquivo para processamento
url = "https://equality-report-service-498552106625.southamerica-east1.run.app/process"

# Preparando os dados do formulário
files = {
    'file': ('sample_data_extended.csv', open('sample_data_extended.csv', 'rb'), 'text/csv')
}

data = {
    'company_name': 'Empresa Teste',
    'k_min': '5',
    'primary_color': '#0F6CBD',
    'accent_color': '#585858',
    'generate_docx': 'false'
}

# Enviando a requisição POST
response = requests.post(url, files=files, data=data)

# Verificando a resposta
print(f"Status Code: {response.status_code}")
print(f"Headers: {response.headers}")
print(f"Content: {response.content[:200]}...")  # Mostrando apenas os primeiros 200 caracteres