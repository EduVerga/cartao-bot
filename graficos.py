"""
Módulo para gerar gráficos de gastos
"""
import matplotlib
matplotlib.use('Agg')  # Backend sem interface gráfica
import matplotlib.pyplot as plt
import io
from typing import List
from database import Caixinha

def gerar_grafico_pizza(caixinhas: List[Caixinha]) -> io.BytesIO:
    """
    Gera gráfico de pizza mostrando distribuição de gastos por caixinha
    """
    # Dados
    labels = [c.nome for c in caixinhas]
    sizes = [c.gasto_atual for c in caixinhas]

    # Cores baseadas no percentual usado
    colors = []
    for c in caixinhas:
        perc = c.percentual_usado
        if perc < 50:
            colors.append('#4CAF50')  # Verde
        elif perc < 80:
            colors.append('#FFC107')  # Amarelo
        else:
            colors.append('#F44336')  # Vermelho

    # Criar figura
    plt.figure(figsize=(10, 8))
    plt.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%',
            startangle=90, textprops={'fontsize': 12, 'weight': 'bold'})
    plt.title('Distribuição de Gastos por Caixinha', fontsize=16, weight='bold', pad=20)

    # Adiciona legenda com valores
    legend_labels = [f'{c.nome}: R$ {c.gasto_atual:.2f}' for c in caixinhas]
    plt.legend(legend_labels, loc='upper left', bbox_to_anchor=(1, 1))

    plt.tight_layout()

    # Salvar em buffer
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
    buffer.seek(0)
    plt.close()

    return buffer


def gerar_grafico_barras(caixinhas: List[Caixinha]) -> io.BytesIO:
    """
    Gera gráfico de barras comparando gasto atual vs limite
    """
    import numpy as np

    # Dados
    labels = [c.nome for c in caixinhas]
    gastos = [c.gasto_atual for c in caixinhas]
    limites = [c.limite for c in caixinhas]

    x = np.arange(len(labels))
    width = 0.35

    # Criar figura
    fig, ax = plt.subplots(figsize=(12, 7))

    # Barras
    bars1 = ax.bar(x - width/2, gastos, width, label='Gasto Atual',
                   color='#2196F3', alpha=0.8)
    bars2 = ax.bar(x + width/2, limites, width, label='Limite',
                   color='#4CAF50', alpha=0.8)

    # Configurações
    ax.set_xlabel('Caixinhas', fontsize=12, weight='bold')
    ax.set_ylabel('Valor (R$)', fontsize=12, weight='bold')
    ax.set_title('Gastos Atual vs Limite por Caixinha', fontsize=16, weight='bold', pad=20)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha='right')
    ax.legend(fontsize=11)
    ax.grid(axis='y', alpha=0.3)

    # Adiciona valores nas barras
    for bar in bars1:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'R$ {height:.0f}',
                ha='center', va='bottom', fontsize=9, weight='bold')

    for bar in bars2:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'R$ {height:.0f}',
                ha='center', va='bottom', fontsize=9, weight='bold')

    plt.tight_layout()

    # Salvar em buffer
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
    buffer.seek(0)
    plt.close()

    return buffer


def gerar_grafico_percentual(caixinhas: List[Caixinha]) -> io.BytesIO:
    """
    Gera gráfico de barras horizontais mostrando % usado de cada caixinha
    """
    # Dados
    labels = [c.nome for c in caixinhas]
    percentuais = [c.percentual_usado for c in caixinhas]

    # Cores baseadas no percentual
    colors = []
    for perc in percentuais:
        if perc < 50:
            colors.append('#4CAF50')  # Verde
        elif perc < 80:
            colors.append('#FFC107')  # Amarelo
        else:
            colors.append('#F44336')  # Vermelho

    # Criar figura
    fig, ax = plt.subplots(figsize=(10, 8))

    # Barras horizontais
    y_pos = range(len(labels))
    bars = ax.barh(y_pos, percentuais, color=colors, alpha=0.8)

    # Configurações
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels, fontsize=11)
    ax.set_xlabel('Percentual Usado (%)', fontsize=12, weight='bold')
    ax.set_title('Percentual de Uso por Caixinha', fontsize=16, weight='bold', pad=20)
    ax.set_xlim(0, 110)
    ax.grid(axis='x', alpha=0.3)

    # Linha de referência em 100%
    ax.axvline(x=100, color='red', linestyle='--', alpha=0.7, linewidth=2)

    # Adiciona valores e informações nas barras
    for i, (bar, perc, c) in enumerate(zip(bars, percentuais, caixinhas)):
        width = bar.get_width()

        # Emoji de status
        emoji = '🟢' if perc < 50 else '🟡' if perc < 80 else '🔴'

        # Texto dentro da barra se couber, senão fora
        if width > 10:
            ax.text(width - 5, i, f'{emoji} {perc:.1f}%',
                    ha='right', va='center', fontsize=10, weight='bold', color='white')
        else:
            ax.text(width + 2, i, f'{emoji} {perc:.1f}%',
                    ha='left', va='center', fontsize=10, weight='bold')

        # Valor gasto/limite do lado direito
        info_text = f'R$ {c.gasto_atual:.2f} / R$ {c.limite:.2f}'
        ax.text(105, i, info_text,
                ha='left', va='center', fontsize=9, style='italic')

    plt.tight_layout()

    # Salvar em buffer
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
    buffer.seek(0)
    plt.close()

    return buffer
