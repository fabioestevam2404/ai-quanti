# Arquitetura

Documentação arquitetural seguindo o **C4 Model** (Simon Brown).

| Nível | Diagrama | Descrição |
|---|---|---|
| C1 | [Contexto](c4/c1-context.md) | Sistema, usuários e integrações externas |
| C2 | [Container](c4/c2-container.md) | Módulos internos e como se comunicam |
| C3 | Componente | *(a detalhar por módulo, conforme cada um evoluir — ex: `backtesting-engine/docs/c3-componentes.md`)* |
| C4 | Código | *(opcional — diagramas de classe pontuais quando a complexidade justificar)* |

Diagramas C3 (componentes internos de um módulo) não vivem aqui — cada módulo
mantém o seu próprio quando fizer sentido, para não acoplar a documentação de
detalhe à visão macro da plataforma.

Ver também: [ADRs](../adr/README.md) para o "porquê" por trás de cada decisão
refletida nestes diagramas.
