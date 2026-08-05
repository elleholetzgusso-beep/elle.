ddd

## extrair_arquivos.py

Junta todos os arquivos que estao espalhados em subpastas dentro de uma unica pasta.

```bash
# copia tudo de fotos/ (e subpastas) para tudo_junto/
python extrair_arquivos.py fotos/ tudo_junto/

# ve o que aconteceria, sem mexer em nada
python extrair_arquivos.py fotos/ tudo_junto/ --simular

# move em vez de copiar e apaga as subpastas que ficarem vazias
python extrair_arquivos.py fotos/ tudo_junto/ --mover --limpar-vazias

# so alguns tipos de arquivo
python extrair_arquivos.py docs/ so_pdfs/ --ext .pdf .docx

# mantem o caminho no nome: sub/pasta/foto.jpg vira sub_pasta_foto.jpg
python extrair_arquivos.py fotos/ tudo_junto/ --prefixo-pasta
```

Opcoes:

| Opcao | O que faz |
| --- | --- |
| `--mover` | move os arquivos em vez de copiar |
| `--conflito renomear\|pular\|sobrescrever` | o que fazer com nomes repetidos (padrao: `renomear`, que gera `foto_1.jpg`) |
| `--ext .jpg .png` | filtra por extensao |
| `--incluir-ocultos` | tambem pega arquivos e pastas que comecam com ponto |
| `--prefixo-pasta` | usa o caminho no nome final |
| `--separador` | separador do `--prefixo-pasta` (padrao: `_`) |
| `--simular` | mostra o plano sem alterar o disco |
| `--limpar-vazias` | remove as subpastas vazias depois de mover |

So precisa do Python 3 instalado, sem bibliotecas extras.
