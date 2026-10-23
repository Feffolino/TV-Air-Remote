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

La modalità dipende da quante mani vede la webcam: **una mano = TV**,
**due mani = Navigazione**. Si entra in Navigazione dopo 0,4 s con due mani e
se ne esce dopo 1,5 s con una mano sola, così una mano persa per un attimo
non cambia modalità.

Il **palmo aperto** fa da joystick. Tienilo fermo per circa 0,3 s: quel punto
diventa il centro (riquadro grigio a schermo). Spostalo di poco in su, in giù,
a sinistra o a destra: il comando parte subito e, se resti lì, si ripete. Più
ti allontani dal centro, più si ripete in fretta: appena oltre il riquadro una
volta ogni 0,7 s circa, lontano fino a 0,15 s. Tornando al centro si ferma;
passando da destra a sinistra cambia subito direzione. Chiudendo o togliendo
la mano il centro si azzera.

Con **due mani in Navigazione** ognuna ha il suo joystick: la mano a sinistra
nell'immagine fa sinistra, su e giù, quella a destra fa destra, su e giù.
Spostare una mano verso l'altra non fa nulla. Su e giù fatti con entrambe
contano una volta sola. Se la webcam perde una delle due mani, quella che
resta fa tutte le direzioni.

### Modalità TV (una mano)

| Gesture | Comando |
|---|---|
| Palmo su / giù | volume + / − (tenuto si ripete, più veloce se ti allontani) |
| Palmo a destra / sinistra | canale successivo / precedente |
| Chiudi e riapri la mano (clic) | OK, che nei video fa pausa / play |
| Pollice su / giù (tenuto) | volume + / − (alternativa al palmo) |
| Pugno, tenuto 1 s | apre la Home |
| 🤟 (pollice, indice e mignolo), tenuto 1,5 s | accende / spegne |

### Modalità Navigazione (due mani)

| Gesture | Comando |
|---|---|
| Palmo su / giù / sinistra / destra | frecce |
| Chiudi e riapri la mano (clic) | OK |
| Pollice su | OK (alternativa al clic) |
| Pollice verso sinistra (dita chiuse) | indietro |
| Vittoria ✌ | indietro (alternativa) |
| Pollice giù | volume − |
| 🤟 tenuto 1,5 s | accende / spegne |

Il pugno tenuto qui non fa nulla.

Un comando singolo (pugno, 🤟, OK, indietro) vale una volta: per ripeterlo
lascia la gesture per almeno mezzo secondo.

Tutte le associazioni e le soglie si possono cambiare nelle sezioni
`mapping` e `thresholds` di `config.yaml`.

## Consigli d'uso

- Stai a 1-3 metri dalla webcam, con le mani ben visibili e non in controluce.
- Fai le gesture con calma: una gesture vale dopo circa 0,2 s di stabilità.
- Se una gesture viene riconosciuta a fatica, abbassa leggermente
  `thresholds.min_score` (es. 0.6); se ci sono comandi indesiderati, alzalo.
- Se il palmo fa scattare comandi con movimenti troppo piccoli, alza
  `thresholds.palm_zone`; se devi spostarlo troppo, abbassalo.

## Checklist di prova (`--dry-run`)

Avvia `python -m tv_air_remote --dry-run` e verifica che nel terminale compaia
il tasto atteso:

- [ ] Una mano: palmo fermo, poi spostato in su → `KEY_VOLUP`; in giù → `KEY_VOLDOWN`
- [ ] Una mano: palmo a destra → `KEY_CHUP`; a sinistra → `KEY_CHDOWN`
- [ ] Palmo tenuto in su → `KEY_VOLUP` ripetuto; tornato al centro → si ferma
- [ ] Palmo in diagonale → resta la direzione iniziata, senza alternarsi
- [ ] Mano che si muove senza fermarsi prima → nessun tasto
- [ ] Pollice su tenuto 3 s → `KEY_VOLUP` ripetuto, più veloce dopo 1,5 s
- [ ] Pollice su, poi mano fuori inquadratura → il volume si ferma subito
- [ ] Clic durante un video (YouTube, Netflix…) → `KEY_ENTER`, il video va in pausa
- [ ] 🤟 per meno di 1,5 s → nessun tasto; per più di 1,5 s → `KEY_POWER`
- [ ] Pugno 1 s → `KEY_HOME` una sola volta, anche tenendolo chiuso
- [ ] Palmo chiuso e riaperto in fretta → `KEY_ENTER`, in entrambe le modalità
- [ ] Seconda mano in vista → `Modalita' -> nav` nel log e overlay "Navigazione"
- [ ] In Navigazione: mano sinistra verso sinistra → `KEY_LEFT`, mano destra
      verso destra → `KEY_RIGHT`, una delle due in su/giù → `KEY_UP`/`KEY_DOWN`;
      mani una verso l'altra → nessun tasto; pollice su → `KEY_ENTER`;
      pollice verso sinistra → `KEY_RETURN` (non la Home, non un clic)
- [ ] Palmo appena oltre il riquadro → frecce lente; lontano → frecce veloci
- [ ] Togliendo la seconda mano → `Modalita' -> tv`

## Risoluzione problemi

| Problema | Soluzione |
|---|---|
| Overlay "TV: non connessa" | Controlla IP e che PC e TV siano sulla stessa rete. Il programma riprova da solo. |
| Overlay "accesso negato" | Riabilita il dispositivo (vedi *Primo collegamento*), poi riavvia. |
| La TV non si accende con 🤟 | Serve `tv.mac` e l'accensione da rete attiva sulla TV. |
| "Impossibile aprire la webcam" | Chiudi altre app che la usano, oppure prova `--camera 1`. |
| "Non disponibile" mettendo in pausa un canale in diretta | Il timeshift Samsung richiede spesso una chiavetta USB collegata alla TV. Nelle app video la pausa col clic funziona. |
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
| `joystick.py` | palmo aperto come joystick (centro e 4 direzioni) |
| `interpreter.py` | macchina a stati: gesture → tasti |
| `tv.py` | collegamento alla TV, riconnessione, Wake-on-LAN |
| `overlay.py` | informazioni a schermo |
| `__main__.py` | avvio e ciclo principale |

Design e piano: `docs/superpowers/specs/` e `docs/superpowers/plans/`.
