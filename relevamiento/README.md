# Relevamiento nacional

`instituciones.json` is the Ministry of Education's official list of the
institutions of the national university system (May 2026), each with whether
Rumbo already publishes it. It is the checklist of the national survey: every
institution ends up `cargada`, or with the reason it cannot be read from its
own site (a bot block, no public list of careers, a site that is down).

`convenios_fuentes.json` lists, for each university, the foreign universities
it has an agreement with and the page that states each one (a list, a news
item, a resolution, a report). It is where to look, not the data:
`load_convenios --relevados` reads every page with the scraper's client and
keeps a partner only while its page still names it. A page that is not the
university's own must also name the university.
