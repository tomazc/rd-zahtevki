import os
from collections import namedtuple
import altair as alt
import math
import pandas as pd
import streamlit as st

import calculations

__version__ = "1.0.2 (2026-02-11)"

f"""
# Zahtevki ARIS
verzija {__version__}

*Tomaž Curk, UL FRI, 2024*

### Oblika vhodne datoteke
Program sprejme datoteko v formatu Excel (`.xlsx`). Datoteka mora vsebovati naslednje zavihke:

- FN: celoletni finančni načrt. Za vsak PPS v svoji vrstici navedi: Plače, Prispevki, MS, AM
- najave: najave sredstev za vsak mesec v letu. Za vsak mesec v svoji vrstici navedi: Plače, Prispevki, MS, AM
- fakturirano: že prejeta sredstva za vsak mesec in PPS. Za vsak PPS in mesec v svoji vrstici navedi: Plače, Prispevki, MS, AM
"""

with open('./primer.xlsx', "rb") as example_file:
    example_byte = example_file.read()
    st.download_button(
        label="Prenesi primer vhodne datoteke Excel",
        data=example_byte,
        file_name="primer.xlsx",
        mime="application/vnd.ms-excel"
    )

"""
Obvezni stolpci so označeni s sivo barvo.

### Opis delovanja
Program dela na dva načina:

1. Za mesece, ki so že bili fakturirani, program preveri pravilnost fakturiranih zneskov za vsak PPS in mesec ter izpiše morebitne napake oz. neujemanja.

2. Za vsak mesec, naveden v najavah, ki še ni bil fakturiran, program za vsak PPS izračuna zneske za plače, prispevke, MS in AM. Sredstva v najavah razporedi med PPS glede na razmerje med fakturiranimi in najavljenimi zneski. V primeru, da je za nek PPS v najavah navedenih manj sredstev, kot je bilo fakturiranih, program izračuna t.i. "negativen zahtevek."


## Uporabi

Naloži datoteko v formatu Excel (`.xlsx`) in izračun se bo zagnal samodejno.

Po končanem izračunu se bo prikazal gumb "Prenesi izračunane zahtevke" za prenos v obliki datoteke Excel (`.xlsx`).
"""

fdata = st.file_uploader("Naloži datoteke Excel", type={"xlsx"})

if fdata:
    FN, najave, fakturirano, meseci, ret_log = calculations.read_data(fdata)

    st.write("## Podatki prebrani")
    st.write(f'Ime naložene datoteke: {fdata.name}')
    st.write(f'Podatki za mesece: {", ".join(meseci)}')

    st.write("## Izračun zahtevkov")
    zahtevki, file_to_download, ret_log, critical_errors = calculations.calculate(FN, najave, fakturirano, meseci)

    if critical_errors:
        st.write("### Kritične napake")
        for e in critical_errors:
            st.write(e)

    st.download_button(
    label="Prenesi izračunane zahtevke",
    data=file_to_download,
    file_name=f"{os.path.splitext(os.path.basename(fdata.name))[0]}-odprti_zahtevki.xlsx"
    )

    st.write("### Log")
    st.write("\n\n".join(ret_log))
