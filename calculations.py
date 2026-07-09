import io
import pandas
import decimal

decimal.getcontext().prec = 100


def remove_exponent(num):
    num = num.quantize(decimal.Decimal("0.01"))
    if num == num.to_integral():
        num = num.quantize(decimal.Decimal("1.00"))
        return num
    num = num.normalize()
    return num


# preberi podatke
# fn_budget = f"budget_{suffix}.xlsx"
# fn_odprti_zahtevki = f"odprti_zahtevki_{suffix}.xlsx"

# vrstni red kategorij, ki se uporablja pri izpisu in preverjanju
kategorije = ["Plače", "Prispevki", "MS", "AM"]

# preberi finančni načrt
def read_data(fn_budget):
    ret_log = []
    xls = pandas.ExcelFile(fn_budget)
    sheet_name = xls.sheet_names[0]
    ret_log.append(f"Reading sheet: {sheet_name}.")
    df = xls.parse(sheet_name)
    df = df.fillna("")  # fill empty cells with empty string '', not nan
    d = df.to_dict()

    cols = ["PPS"] + kategorije
    tabular_data = list(zip(*[d[c].values() for c in cols]))
    FN = {}
    for rp, place, prispevki, ms, am in tabular_data:
        assert rp == rp.strip()
        place = remove_exponent(decimal.Decimal(place))
        prispevki = remove_exponent(decimal.Decimal(prispevki))
        ms = remove_exponent(decimal.Decimal(ms))
        am = remove_exponent(decimal.Decimal(am))
        v = (place, prispevki, ms, am)
        assert FN.setdefault(rp, v) == v

    # preberi najave
    xls = pandas.ExcelFile(fn_budget)
    sheet_name = xls.sheet_names[1]
    ret_log.append(f"Reading sheet: {sheet_name}.")
    df = xls.parse(sheet_name)
    df = df.fillna("")  # fill empty cells with empty string '', not nan
    d = df.to_dict()

    cols = ["Mesec"] + kategorije
    tabular_data = list(zip(*[d[c].values() for c in cols]))
    najave = {}
    meseci = []
    for mesec, place, prispevki, ms, am in tabular_data:
        place = remove_exponent(decimal.Decimal(place))
        prispevki = remove_exponent(decimal.Decimal(prispevki))
        ms = remove_exponent(decimal.Decimal(ms))
        am = remove_exponent(decimal.Decimal(am))
        v = (place, prispevki, ms, am)
        assert najave.setdefault(mesec, v) == v

        assert mesec not in meseci
        meseci.append(mesec)

    ret_log.append(meseci)

    # preberi fakturirano
    xls = pandas.ExcelFile(fn_budget)
    sheet_name = xls.sheet_names[2]
    ret_log.append(f"Reading sheet: {sheet_name}.")
    df = xls.parse(sheet_name)
    df = df.fillna("")  # fill empty cells with empty string '', not nan
    d = df.to_dict()

    cols = ["PPS", "Mesec"] + kategorije
    tabular_data = list(zip(*[d[c].values() for c in cols]))
    fakturirano = {}
    fakturirano_byrp = {}
    for rp, mesec, place, prispevki, ms, am in tabular_data:
        assert rp == rp.strip()
        place = remove_exponent(decimal.Decimal(place))
        prispevki = remove_exponent(decimal.Decimal(prispevki))
        ms = remove_exponent(decimal.Decimal(ms))
        am = remove_exponent(decimal.Decimal(am))
        v = (place, prispevki, ms, am)
        assert fakturirano.setdefault(mesec, {}).setdefault(rp, v) == v

        # update fakturirano_byrp
        fak_vsota = fakturirano_byrp.get(rp, (0, 0, 0, 0))
        fak_vsota = list(x + y for x, y in zip(fak_vsota, v))
        fakturirano_byrp[rp] = fak_vsota

    return FN, najave, fakturirano, fakturirano_byrp, meseci, ret_log


# izračunaj zahtevek
def calculate(FN, najave, fakturirano, fakturirano_byrp, meseci):
    ret_log = []
    critical_errors = []
    vsota_fakturirano = {}

    def f_money(x):
        # values are money, should use comma for decimal place, and dot for thousdands separator
        return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    def nice_format(vals):
        # values are money, should use comma for decimal place, and dot for thousdands separator
        return ", ".join([f"{k}: {f_money(x)}" for k, x in zip(kategorije, vals)]+[f"vsota: {f_money(sum(vals))}"])

    def update_vsota_fakturirano(fakturirano_mesec):
        for rp, fak_mesec in fakturirano_mesec.items():
            fak_vsota = vsota_fakturirano.get(rp, (0, 0, 0, 0))
            fak_vsota = list(x + y for x, y in zip(fak_vsota, fak_mesec))
            vsota_fakturirano[rp] = fak_vsota

    def sum_fakturirano(fakturirano_rp):
        return tuple([sum(x) for x in list(zip(*fakturirano_rp))])

    def scale_vals(v_ref, v_vals, neg_fak):
        # v_ref is the amount to be distributed
        # v_vals is the difference between current fakturirano and FN (FN - fakturirano)
        #  if v_vals is negative, it means that fakturirano is higher than FN, and the difference has to be taken and moved to other projects within the same category.
        #      If there is some remaining amount, it should be moved to other categories.
        #
        #  if v_vals is positive, it means that fakturirano is lower than FN, and the amount has to be distributed proportionally to the differences.
        v_vals_sum = sum(v_vals) # current sum of differences

        # separate negative and positive differences
        #   negative difference: take from the account
        #   positive diffrence: distribute proportionally
        v_neg_sum = sum([v for v in v_vals if v <= decimal.Decimal(0.0)])
        i_skip_neg = [i for i, v in enumerate(v_vals) if v <= decimal.Decimal(0.0)]

        exact_vals = []
        for v, n in zip(v_vals, neg_fak):
            if v <= decimal.Decimal(0.0) or n == True:
                v = v  # do not modify negative values, the entire amount has to be taken from account
            else:
                # the negative part has to be subdivided among the positive values
                diff = (v_vals_sum + (-v_neg_sum))
                if diff == 0.0:
                    v = decimal.Decimal(0.0)
                else:
                    v = (v_ref + (-v_neg_sum)) * v / diff
            exact_vals.append(v)

        rounded_vals = [remove_exponent(decimal.Decimal(v))
                        for v in exact_vals]

        while sum(rounded_vals) != v_ref:
            dif = [(x - y, i) for (i, (x, y)) in enumerate(zip(exact_vals,
                                                               rounded_vals)) if i not in i_skip_neg]
            if not dif:
                break

            rounded_dif = sum(rounded_vals) - v_ref
            if rounded_dif > 0:
                # i = dif.index(min(dif))
                _, i = max(dif)
                rounded_vals[i] -= decimal.Decimal(0.01)  # -= rounded_dif
            elif rounded_dif < 0:
                # i = dif.index(max(dif))  # dif.index(min(dif))
                _, i = min(dif)
                rounded_vals[i] += decimal.Decimal(0.01)  # -= rounded_dif
            rounded_vals = [remove_exponent(
                decimal.Decimal(v)) for v in rounded_vals]

        return rounded_vals

    zahtevek = {}
    records_zahtevek = []
    odprti_meseci = []
    for mesec in meseci:
        ret_log.append(f'#### {mesec}')
        if mesec in fakturirano:
            ret_log.append("... že fakturirano")
            if mesec in najave:
                ret_log.append("preverjanje ujemanja najave in fakturiranega")
                na = najave[mesec]
                fa = tuple([sum(x)
                           for x in list(zip(*fakturirano[mesec].values()))])
                if na == fa:
                    ret_log.append("se ujema")
                else:
                    na_str = ", ".join([f"{k}: {f_money(x)}" for k, x in zip(kategorije, na)]+[f"vsota: {f_money(sum(na))}"])
                    fa_str = ", ".join([f"{k}: {f_money(x)}" for k, x in zip(kategorije, fa)]+[f"vsota: {f_money(sum(fa))}"])
                    ret_log.append("pozor, se NE ujema")
                    ret_log.append("najava:")
                    ret_log.append(f"\t{na_str}")
                    ret_log.append("fakturirano:")
                    ret_log.append(f"\t{fa_str}")
                    critical_errors.append(f"{mesec}: zneski najave {na_str} in fakturirano {fa_str} se ne ujemajo. Preveri FN, najave in fakturirano za izdane zahtevke.")
                update_vsota_fakturirano(fakturirano[mesec])
            else:
                ret_log.append("napaka... za mesec ni najave")
        else:
            if mesec not in najave:
                ret_log.append("napaka... za mesec ni podatkov o najavah")
                assert mesec in najave

            odprti_meseci.append(mesec)
            ret_log.append("... izračun zneskov za zahtevek")
            # calculate difference between expected FN and current running sum of fakturirano
            rps = []
            dif_vals = []
            neg_fak_vals = []
            for rp, fn_vrednosti in FN.items():
                fak_vrednosti = vsota_fakturirano.get(rp, (decimal.Decimal(
                    0.0), decimal.Decimal(0.0), decimal.Decimal(0.0), decimal.Decimal(0.0)))
                dif_vrednosti = list(
                    x - y for x, y in zip(fn_vrednosti, fak_vrednosti))
                rps.append(rp)
                dif_vals.append(dif_vrednosti)
                neg_fak_vals.append([v < 0 for v in fak_vrednosti])
            dif_vals = list(zip(*dif_vals))
            neg_fak_vals = list(zip(*neg_fak_vals))

            scaled_vals = []
            for v_najave, v_dif, neg_fak in zip(najave[mesec], dif_vals, neg_fak_vals):
                scaled_v_dif = scale_vals(v_najave, v_dif, neg_fak)
                scaled_vals.append(scaled_v_dif)

            zahtevek[mesec] = {}
            for rp, scaled_vrednosti in zip(rps, zip(*scaled_vals)):
                zahtevek[mesec][rp] = scaled_vrednosti
                records_zahtevek.append(
                    [rp, mesec] + list([float(x) for x in scaled_vrednosti])
                )

            ret_log.append("preverjanje ujemanja najave in zahtevka")
            na = najave[mesec]
            za = tuple([sum(x) for x in list(zip(*zahtevek[mesec].values()))])
            if na == za:
                ret_log.append("se ujema")
            else:
                na_str = ", ".join([f"{k}: {f_money(x)}" for k, x in zip(kategorije, na)]+[f"vsota: {f_money(sum(na))}"])
                za_str = ", ".join([f"{k}: {f_money(x)}" for k, x in zip(kategorije, za)]+[f"vsota: {f_money(sum(za))}"])
                ret_log.append("pozor, se NE ujema")
                ret_log.append("najava:")
                ret_log.append(f"\t{na_str}\n")
                ret_log.append("zahtevek:")
                ret_log.append(f"\t{za_str}")
                critical_errors.append(f"{mesec}: zneski najave {na_str} in zahtevka {za_str} se ne ujemajo. Preveri FN, prejete najave in izračunane zahtevke.")
            update_vsota_fakturirano(zahtevek[mesec])

        ret_log.append('')

    # save to disk
    file_to_download = io.BytesIO()
    df1 = pandas.DataFrame(
        records_zahtevek, columns=["PPS", "Mesec"] + kategorije
    )
    writer = pandas.ExcelWriter(file_to_download, engine="xlsxwriter")
    df1.to_excel(writer, index=False, sheet_name="zahtevki")
    workbook = writer.book
    worksheet = writer.sheets["zahtevki"]
    format1 = workbook.add_format({"num_format": "0.00"})
    format1.set_align("right")
    worksheet.set_column("A:A", 50)
    worksheet.set_column("C:C", None, format1)
    worksheet.set_column("D:D", None, format1)
    worksheet.set_column("E:E", None, format1)
    worksheet.set_column("F:F", None, format1)
    writer.close()
    ret_log.append('')

    ret_log.append("### Preverjanje, ali bodo fakturirani zneski po izdanih novih zahtevkih znotraj finančnega načrta.")
    for rp, vals_fak in vsota_fakturirano.items():
        vals_FN = FN[rp]
        ret_log.append(f"#### {rp}")
        ret_log.append(f"finančni načrt:          ")
        ret_log.append(f"\t{nice_format(vals_FN)}")
        ret_log.append(f"fakturirano pred izdajo odprtih zahtevkov:")
        ret_log.append(f"\t{nice_format(fakturirano_byrp.get(rp, [0, 0, 0, 0]))}")
        for mesec in odprti_meseci:
            ret_log.append(f'odprt zahtevek za: {mesec}')
            ret_log.append(f'\t{nice_format(zahtevek[mesec][rp])}')
        ret_log.append(f"bo fakturirano po prejemu odprtih zahtevkov:")
        ret_log.append(f"\t{nice_format(vals_fak)}")
        within_FN = all(x <= y for x, y in zip(vals_fak, vals_FN))
        nonnegative_FN = all(x >= 0.0 for x in vals_fak)
        equal_to_FN = all(x == y for x, y in zip(vals_fak, vals_FN))
        if within_FN and nonnegative_FN:
            if equal_to_FN:
                ret_log.append("finančni načrt dosežen")
            else:
                ret_log.append("znotraj finančnega načrta")
        else:
            if not nonnegative_FN:
                ret_log.append("NAPAKA, po izvedenih zahtevkih bo fakturirano stanje negativno")
                critical_errors.append(
                    f"{rp}: po izvedenih zahtevkih bo fakturirano stanje negativno.")
            else:
                ret_log.append(
                    "NAPAKA, po izvedenih zahtevkih bo fakturirano višje od finančnega načrta"
                )
                critical_errors.append(
                    f"{rp}: po izvedenih zahtevkih bo fakturirano višje od finančnega načrta.")
        ret_log.append('')
    ret_log.append("KONEC")
    return records_zahtevek, file_to_download, ret_log, critical_errors