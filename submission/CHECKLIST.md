# Checklist manual — DataNova 2026 (Penumbra)

Lo que el agente **no** hizo (a propósito) y debe hacer Adrian u otro agente. Orden sugerido.

## 0. Urgente / riesgos de elegibilidad (hacer HOY)
- [ ] **Elegibilidad contradictoria.** La barra lateral de Devpost dice *"Students only"* y *"Team required"*, pero las reglas oficiales y datanovathon.com dicen que pueden participar profesionales, desarrolladores e individuos. Escribir a **contact@datanovathon.com** (o usar el foro de Devpost) y pedir confirmación por escrito de que un participante individual y no estudiante es elegible. Si exigen ser estudiante o equipo: inscribirse como estudiante solo si es verdad, o sumar a un compañero estudiante (y actualizar "Team contributions").
- [ ] **Registro en Unstop.** datanovathon.com pide registrarse en Unstop (tarifa de ₹100 INR por participante) y elegir el problem statement al registrarse. En la web, el **30 Oct 2026** figura como *"Problem Statement Deadline"*. Elegir **DN-SU-01 — Solar Energy Generation Forecasting** (track Sustainability). Enlace de registro: https://unstop.com/o/I8wokZ9
- [ ] Registrarse en Devpost: https://datanova-2026-global-data-thon.devpost.com/ (lo hace otro agente o el usuario).

## 1. Verificar que todo funciona (5 min)
- [ ] Abrir la demo: **https://skkippie.me/penumbra-solar-forecast/** (espejo: https://s-kkipie.github.io/penumbra-solar-forecast/, que redirige al dominio propio). Probar en el móvil y en el escritorio; probar el modo oscuro (botón ◐).
- [ ] Repo: **https://github.com/S-kkipie/penumbra-solar-forecast** — debe verse el README con el diagrama.
- [ ] Pestaña **Actions** del repo: el workflow `daily-forecast-and-pages` debe correr cada día (10:30, 11:20 y 07:00 UTC). Si alguna corrida falla, abrirla, leer el log y relanzar con *Run workflow*. GitHub desactiva los cron tras 60 días sin actividad (no aplica aquí porque el bot hace commits diarios).
- [ ] Antes de enviar (≈10 nov), comprobar que la sección **Live track record** ya tiene varios días puntuados. Si la Action no corrió algún día, ese día queda sin pronóstico (no se puede rellenar después: el log es de solo-anexar y eso es parte del argumento de honestidad).

## 2. Video (opcional en las reglas, pero muy recomendable) — ~3 min
- [ ] Grabar siguiendo `submission/VIDEO_SCRIPT.md` (pantalla + voz; OBS o Loom). Inglés recomendado (jurado internacional).
- [ ] Subir a YouTube como *Unlisted* o *Public* (Devpost acepta YouTube/Vimeo). Copiar el enlace.

## 3. PPT (obligatorio)
- [ ] El deck está en `submission/Penumbra_DataNova2026.pptx` (y `submission/Penumbra_DataNova2026.pdf`). Abrirlo en PowerPoint/Google Slides y revisar rápido que se vea bien en tu equipo.
- [ ] Subirlo a Google Drive (o OneDrive) con permiso *"Cualquiera con el enlace puede ver"*, y/o adjuntar el PDF en Devpost. Copiar el enlace.

## 4. Envío en Devpost (antes del **10 nov 2026, 17:00 hora de Perú** = 11 nov 03:30 IST)
- [ ] Copiar los textos de `submission/DEVPOST.md` en los campos correspondientes (título, tagline, descripción, "Built with").
- [ ] Enlaces: demo, repo, video, PPT.
- [ ] Imagen de portada / galería: usar `docs/figures/dashboard.png`, `docs/figures/example_day.png`, `docs/figures/monthly_nmae.png`, `docs/figures/coverage_by_regime.png`.
- [ ] Track / problema: **Sustainability — DN-SU-01**.
- [ ] Team contributions: Adrian Issac Mamani Quispe — todo el proyecto (ver texto en DEVPOST.md). Si se suma alguien, actualizar.
- [ ] Revisar que todos los enlaces abran en una ventana de incógnito antes de pulsar *Submit*.

## 5. Ronda 2 (25 nov 2026) — si quedas preseleccionado
- [ ] Presentación en vivo: usar el mismo deck; abrir la demo en vivo (la sección "Tomorrow" mostrará el pronóstico de ese día y el track record tendrá ~25 días).
- [ ] Preguntas probables y respuestas cortas están al final de `submission/VIDEO_SCRIPT.md`.

## Notas
- Licencias: Elia Open Data Licence; Open-Meteo (CC BY 4.0, API gratuita no comercial — OK para un proyecto de concurso); Energy-Charts/SMARD (CC BY 4.0). Todo citado en README.
- No hay claves ni secretos en el repo; la Action usa solo `GITHUB_TOKEN`.
- Para reproducir todo localmente: ver "Reproduce" en el README (≈15 min descarga + ≈10 min backtest).
