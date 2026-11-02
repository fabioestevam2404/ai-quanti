# Arquitetura

Documentação arquitetural seguindo o **C4 Model** (Simon Brown).

**Comece por [estado-atual.md](estado-atual.md):** o que existe no código
hoje, as camadas de cada módulo, o fluxo de uma ordem no MVP e o pipeline de
CI. Os diagramas C4 abaixo descrevem a arquitetura-alvo completa.

| Nível | Diagrama | Descrição |
|---|---|---|
| C1 | [Contexto](c4/c1-context.md) | Sistema, usuários e integrações externas |
| C2 | [Container](c4/c2-container.md) | Módulos internos e como se comunicam (alvo) |
| C3 | [Componentes da plataforma](c4/c3-components.md) | Integração entre módulos, stores e IA/RAG (alvo) |
| C4 | Código | *(opcional — diagramas de classe pontuais quando a complexidade justificar)* |

Componentes internos de um módulo, quando fizerem sentido, ficam no próprio
módulo (ex.: `backtesting-engine/docs/c3-componentes.md`), para não acoplar a
documentação de detalhe à visão macro da plataforma.

Ver também: [ADRs](../adr/README.md) para o "porquê" por trás de cada decisão
refletida nestes diagramas.
