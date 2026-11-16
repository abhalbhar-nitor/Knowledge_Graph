import streamlit as st

from components.layout import activity, guard, next_stage, run_stage, stage_header
from kg.stages import s02_connect

ctx = stage_header(2)
if guard(ctx, 1):
    mode = st.radio("Data source", ["Sample retail database (in memory, no setup)", "PostgreSQL"],
                    horizontal=True)
    if mode.startswith("Sample"):
        st.info("Same tables and rows as `sql/01_source_schema.sql`, including deliberate data problems "
                "(duplicate customer, orphan order, negative price, undeclared FK) so every stage has "
                "something to show.")
        if st.button("Connect to sample database", type="primary"):
            run_stage(s02_connect.connect_sample, ctx, success="Connected")
    else:
        d = s02_connect.env_defaults()
        with st.form("pg"):
            c1, c2, c3 = st.columns([2, 1, 2])
            host = c1.text_input("Host (prefer a read replica)", d["host"])
            port = c2.number_input("Port", value=int(d["port"]), step=1)
            dbname = c3.text_input("Database", d["dbname"])
            c4, c5, c6 = st.columns(3)
            user = c4.text_input("Read-only user", d["user"])
            password = c5.text_input("Password", d["password"], type="password",
                                     help="Used only for this session; never written to disk or logs.")
            sslmode = c6.selectbox("SSL mode", ["prefer", "require", "verify-full", "disable"],
                                   index=["prefer", "require", "verify-full", "disable"].index(d["sslmode"])
                                   if d["sslmode"] in ("prefer", "require", "verify-full", "disable") else 0)
            schemas = st.text_input("Schemas (comma separated)", ", ".join(d["schemas"]))
            ok = st.form_submit_button("Test & connect", type="primary")
        if ok:
            run_stage(s02_connect.connect_postgres, ctx, host=host, port=int(port), dbname=dbname, user=user,
                      password=password, sslmode=sslmode,
                      schemas=[s.strip() for s in schemas.split(",") if s.strip()], success="Connected")

    if ctx.source_info:
        st.subheader("Connection")
        i = ctx.source_info
        c = st.columns(4)
        c[0].metric("Mode", i["mode"])
        c[1].metric("User", i["user"])
        c[2].metric("Read-only session", "yes" if i["read_only"] else "enforced per session")
        c[3].metric("Server", i["server_version"][:28])
        st.caption("Safety controls: `default_transaction_read_only=on`, `statement_timeout=5 min`, "
                   "connection pool of max 4, `application_name=kg-networkx-builder` for tracing in pg_stat_activity.")
activity(ctx, 2)
next_stage(2)
