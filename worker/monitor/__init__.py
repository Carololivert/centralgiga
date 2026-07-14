"""Monitor SmartOLT embarcado no worker.

Expõe a API (/api/snapshot, /api/pon) numa thread HTTP dentro do próprio
processo do worker — não precisa de um serviço separado. O worker.py chama
`monitor.service.iniciar_em_thread(...)` no arranque (ver worker.py).

Import preguiçoso de propósito: quem importa `monitor.service` deve fazê-lo
DEPOIS do worker/config.py carregar o .env (os clientes SmartOLT/SGP leem as
variáveis no import).
"""
