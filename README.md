# TV Air Remote

Controlla una Smart TV Samsung (Tizen) con le gesture delle mani. Una webcam
collegata al PC riprende la mano, MediaPipe riconosce la gesture in tempo reale
e il programma invia il tasto corrispondente alla TV attraverso la rete.

Pensato per l'uso quotidiano come televisore: cambio canale e volume sono i
comandi più rapidi, la navigazione nei menu è disponibile in una modalità a
parte.

## Requisiti

- Python 3.11 o 3.12
- Una webcam (quella integrata del portatile va bene)
- Una TV Samsung Tizen (modelli dal 2016 in poi) sulla stessa rete del PC
- Su Linux: le librerie `libegl1` e `libgles2` (richieste da MediaPipe)

## Installazione

```bash
git clone https://github.com/Feffolino/TV-Air-Remote.git
cd TV-Air-Remote
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -e .
```

Al primo avvio il modello di riconoscimento (circa 8 MB) viene scaricato in
`models/`.

> Non installare `opencv-python`: MediaPipe usa già `opencv-contrib-python` e
> i due pacchetti insieme si danneggiano a vicenda.

## Configurazione

1. Copia il file di esempio:
   ```bash
   cp config.example.yaml config.yaml
   ```
2. Inserisci l'IP della TV in `tv.host`. Lo trovi sulla TV in
   Impostazioni > Generale > Rete > Stato rete > Impostazioni IP.
   Conviene assegnare alla TV un IP fisso dal router.
3. Facoltativo, per accendere la TV con la gesture: inserisci in `tv.mac` il
   MAC address della TV e attiva sulla TV
   Impostazioni > Generale > Rete > Impostazioni esperto > Accensione con
   dispositivo mobile.

### Primo collegamento

Al primo avvio la TV mostra la richiesta di consentire l'accesso a
"TV Air Remote": conferma con il telecomando. Il permesso viene salvato in
`.tv_token` e non verrà più chiesto.

Se hai rifiutato per errore: Impostazioni > Generale > Gestione dispositivi
esterni > Gestione connessione dispositivi, poi abilita "TV Air Remote".

## Avvio

```bash
python -m tv_air_remote             # usa config.yaml
python -m tv_air_remote --dry-run   # prova le gesture senza toccare la TV
python -m tv_air_remote --camera 1  # usa un'altra webcam
```

Si apre una finestra con l'immagine della webcam, la mano tracciata, la
modalità attiva, la gesture riconosciuta, l'ultimo tasto inviato e lo stato
della TV. Premi `q` o `ESC` per uscire.

## Gesture

Gli swipe partono sempre dal **palmo aperto tenuto fermo per circa 0,3 s**:
poi si sposta la mano con decisione nella direzione voluta. Così un movimento
casuale non cambia canale.

### Modalità TV (predefinita)

| Gesture | Comando |
|---|---|
| Swipe in su / in giù | canale successivo / precedente |
| Pollice su / giù (tenuto) | volume + / −, si ripete e accelera dopo 1,5 s |
| Vittoria ✌ | pausa / play (alternati) |
| Indice su, tenuto 1 s | apre la Home e passa alla modalità Navigazione |
| 🤟 (pollice, indice e mignolo), tenuto 1,5 s | accende / spegne |

Pugno e swipe orizzontali non fanno nulla in questa modalità, apposta.

### Modalità Navigazione

| Gesture | Comando |
|---|---|
| Swipe in su / giù / sinistra / destra | frecce |
| Pugno | OK |
| Vittoria ✌ | indietro |
| Pollice su / giù | volume |
| Indice su, tenuto 1 s | esce e torna alla modalità TV |
| 🤟 tenuto 1,5 s | accende / spegne |

Dopo 8 secondi senza comandi si torna da soli alla modalità TV.

Tutte le associazioni e le soglie si possono cambiare nelle sezioni
`mapping` e `thresholds` di `config.yaml`.

## Consigli d'uso

- Stai a 1-3 metri dalla webcam, con la mano ben visibile e non in controluce.
- Una sola mano: il sistema ne segue una alla volta.
- Fai le gesture con calma: una gesture vale dopo circa 0,2 s di stabilità.
- Se una gesture viene riconosciuta a fatica, abbassa leggermente
  `thresholds.min_score` (es. 0.6); se ci sono comandi indesiderati, alzalo.

## Checklist di prova (`--dry-run`)

Avvia `python -m tv_air_remote --dry-run` e verifica che nel terminale compaia
il tasto atteso:

- [ ] Palmo fermo, poi swipe in su → `KEY_CHUP`
- [ ] Palmo fermo, poi swipe in giù → `KEY_CHDOWN`
- [ ] Swipe a sinistra/destra in modalità TV → nessun tasto
- [ ] Mano che si alza senza fermarsi prima → nessun tasto
- [ ] Pollice su tenuto 3 s → `KEY_VOLUP` ripetuto, più veloce dopo 1,5 s
- [ ] Pollice su, poi mano fuori inquadratura → il volume si ferma subito
- [ ] Vittoria due volte → `KEY_PAUSE`, poi `KEY_PLAY`
- [ ] 🤟 per meno di 1,5 s → nessun tasto; per più di 1,5 s → `KEY_POWER`
- [ ] Indice su 1 s → `KEY_HOME` e overlay "Navigazione"
- [ ] In Navigazione: swipe nelle 4 direzioni → frecce; pugno → `KEY_ENTER`;
      vittoria → `KEY_RETURN`
- [ ] In Navigazione, indice su 1 s → `KEY_EXIT` e ritorno a "TV"
- [ ] In Navigazione, 8 s senza gesture → ritorno a "TV"

## Risoluzione problemi

| Problema | Soluzione |
|---|---|
| Overlay "TV: non connessa" | Controlla IP e che PC e TV siano sulla stessa rete. Il programma riprova da solo. |
| Overlay "accesso negato" | Riabilita il dispositivo (vedi *Primo collegamento*), poi riavvia. |
| La TV non si accende con 🤟 | Serve `tv.mac` e l'accensione da rete attiva sulla TV. |
| "Impossibile aprire la webcam" | Chiudi altre app che la usano, oppure prova `--camera 1`. |
| Play/pausa invertiti | Succede se usi anche il telecomando: ripeti la gesture. |
| La pausa non funziona sui canali in diretta | Il timeshift Samsung richiede spesso una chiavetta USB collegata alla TV. |
| Modello non scaricabile | Scarica a mano l'URL indicato nel messaggio e salvalo in `models/gesture_recognizer.task`. |

## Sviluppo

```bash
pip install -e ".[dev]"
pytest
```

Struttura del pacchetto `tv_air_remote/`:

| File | Ruolo |
|---|---|
| `config.py` | configurazione e validazione |
| `camera.py` | acquisizione dalla webcam |
| `recognizer.py` | MediaPipe Gesture Recognizer |
| `swipe.py` | rilevamento degli swipe |
| `interpreter.py` | macchina a stati: gesture → tasti |
| `tv.py` | collegamento alla TV, riconnessione, Wake-on-LAN |
| `overlay.py` | informazioni a schermo |
| `__main__.py` | avvio e ciclo principale |

Design e piano: `docs/superpowers/specs/` e `docs/superpowers/plans/`.
