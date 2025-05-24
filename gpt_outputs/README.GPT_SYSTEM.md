# Sistema de GPTs

Cada GPT ejecuta pre-flight:
1. Comprueba su carpeta (`gpt_outputs/<nombre>/`).
2. Si no existe, crea `README.md`.
3. Trabaja solo dentro de ella.

## Carpetas reservadas:
- app_planning/
- theme_builder/
- architecture/
- screen_generator/
- state_management/
- testing/
- deployment/
- supervisor/

## Políticas:
✅ No push directo a main → siempre Pull Request.  
✅ Supervisor GPT controla progreso y bloqueos.  
✅ Logs y notificaciones quedan registrados en backend + Slack.  
✅ Backend protegido con rate-limit y secrets.

Este archivo es el contrato base que guía cómo todos los GPTs y humanos deben trabajar sobre este repositorio.
