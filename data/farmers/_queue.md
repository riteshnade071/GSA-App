# Farmers research queue (not loaded by seed_farmers.py — only *.json files are)
Re-check each against the official portal before adding. Nothing below has been verified yet.

## Central
- PM Kisan Maandhan Yojana (farmer pension), Soil Health Card, e-NAM, PM Matsya Sampada Yojana (fisheries), Paramparagat Krishi Vikas Yojana (organic), National Beekeeping & Honey Mission, FPO formation scheme, animal-husbandry KCC.

## Maharashtra
- Nanaji Deshmukh Krishi Sanjivani Prakalp (PoCRA), Birsa Munda Krushi Kranti Yojana (tribal farmers), Dr. Babasaheb Ambedkar Krushi Swavalamban Yojana (SC/NT farmers), Gopinath Munde farmer accident insurance, Magel Tyala Shettale (farm pond on demand).

## Other states
Done so far: Maharashtra, Gujarat, Telangana, Andhra Pradesh, West Bengal, Odisha, Madhya Pradesh.
Still to research (nothing below is verified, none of it is shown on the site):
- Karnataka, Uttar Pradesh, Rajasthan, Tamil Nadu, Kerala, Bihar, Punjab, Haryana, Chhattisgarh, Jharkhand, Assam, Himachal Pradesh, Uttarakhand, Jammu & Kashmir, Goa, the North-East states and the Union Territories.
- Link checks needed: the Odisha (krushak.odisha.gov.in) and Madhya Pradesh (mpkrishi.mp.gov.in) addresses were written from memory of the official sites, not opened. Run `python check_new_sections.py --urls`.

## Update 12 Oct 2026: Kerala (AIMS portal), Tamil Nadu (Agrisnet / Uzhavan portal) added as portal-type entries (they survive government changes). Karnataka still has no farmer entry.
Skipped on purpose (re-check on the official source):
- Kerala Farmers' Welfare Fund pension (Karshaka Kshemanidhi): the new UDF government set up a committee to restructure or merge it (reports, Sep-Oct 2026); first pensions were due from Dec 2026; the proposed Rs 5,000 pension was questioned by the Finance Dept. The separate Kerala pension for small and marginal farmers (reported Rs 1,600 a month, age 60+) needs a fresh check under the new government.
- Tamil Nadu: Kalaignarin All Village Integrated Agricultural Development Programme (may be renamed), free three-phase power for agriculture (budget Rs 7,432 crore, rules not read), new Kuruvai package for delta and non-delta farmers (Rs 134 crore), Rs 17,000 crore crop-loan target, Rs 4,000 an acre organic incentive, Soil Conservation / Millet / Pulses-Oilseed missions (details not yet published as of Aug 2026).
- Karnataka: Krishi Bhagya (farm ponds / irrigation), Raita Siri (millets), Raitamitra portal, Bhoochetana: only one-line third-party descriptions found.

## Update 13 Oct 2026: Bihar (DBT Agriculture portal) and Haryana (Meri Fasal Mera Byora, Bhavantar Bharpai) added. Punjab has no farmer entry yet.
Skipped: Bihar Rajya Fasal Sahayata (the only source read is a 2021 page quoting Rs 7,500 / Rs 10,000 a hectare, current rates and whether it runs this year are unknown); Bihar input-subsidy rates (Rs 8,500-22,500 a hectare from a private site only); Haryana Mukhyamantri Bagwani Bima and other Haryana schemes (not researched); Punjab schemes (not researched).
Open checks: the Meri Fasal Mera Byora address (mfmb.haryana.gov.in was not seen in the sources) and the amounts/crops currently covered by Bhavantar Bharpai (bajra and potato were added in later years).

## Update 13 Oct 2026: PM-KMY pension added (farmers/central_2.json).
Still to add: e-NAM, Soil Health Card, Paramparagat Krishi Vikas Yojana (organic), PM Dhan-Dhaanya Krishi Yojana (new, 100 districts), fisheries (PMMSY, KCC for fishers), animal husbandry / dairy (AHIDF, KCC for animal husbandry), FPO scheme.
