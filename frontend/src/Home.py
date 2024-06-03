import streamlit as st
from astropy.io import fits
from matplotlib import pyplot as plt
from psycopg2 import sql

from src.interfaces import get_postgres_client


@st.cache_data
def fetch_status_data():
    with get_postgres_client().cursor() as cursor:
        cursor.execute(sql.SQL("SELECT status, COUNT(*) FROM galaxies GROUP BY status"))
        results = cursor.fetchall()
        if not results:
            return None
        return results


@st.cache_data
def fetch_galaxy_data(preview_galaxy_id):
    if not preview_galaxy_id:
        return None
    try:
        id_int = int(preview_galaxy_id)
    except ValueError:
        return None
    with get_postgres_client().cursor() as cursor:
        cursor.execute(sql.SQL(f"""
            SELECT * FROM galaxies
            WHERE id={id_int} OR source_id='{preview_galaxy_id}'
        """))
        results = cursor.fetchall()
        if not results:
            return None
        return results[0]


@st.cache_data
def fetch_galaxy_rotation_data(preview_galaxy_id):
    if not preview_galaxy_id:
        return None
    with get_postgres_client().cursor() as cursor:
        cursor.execute(sql.SQL(f"""
            SELECT * FROM fits_data
            WHERE source_id='{preview_galaxy_id}'
        """))
        results = cursor.fetchall()
        if not results:
            return None
        return results[0]


def clear_all_cache():
    fetch_status_data.clear()
    fetch_galaxy_data.clear()
    fetch_galaxy_rotation_data.clear()


st.title("Radon Controller")
with st.sidebar:
    st.button(label="Clear Cache & Refresh", on_click=clear_all_cache)

st.subheader("Galaxy dataset status:")
status_data = fetch_status_data()
st.table({a[0]: a[1] for a in status_data})
with st.expander("Plot"):
    fig, ax = plt.subplots()
    ax.bar([a[0] for a in status_data], [a[1] for a in status_data])
    st.pyplot(fig)

########################
# Data Preview Section #
########################
st.subheader("Galaxy Data Preview")
galaxy_id = st.text_input("Enter galaxy UID or source ID:", placeholder="e.g. 5937148114675443200")
st.session_state.preview_galaxy_id = galaxy_id

if (preview_galaxy_data := fetch_galaxy_data(galaxy_id)) is not None:
    uid, source_id, ra, dec, gal_prob, bin_id, status, failed_attempts = preview_galaxy_data
    st.table({
        "Unique ID": str(uid),
        "Source ID": str(source_id),
        "Right Ascension": str(ra),
        "Declination": str(dec),
        "Galaxy probability": str(gal_prob),
        "Bin ID": str(bin_id),
        "Status": str(status),
        "Failed attempts": str(failed_attempts)
    })

    # Display FITS data
    if status == "Fetched" or status == "Transformed":
        path = f"../data/fits/b{bin_id}/{source_id}.fits"
        with fits.open(path) as hdu_list:
            data = hdu_list[0].data

        rotations = None
        if status == "Transformed":
            _, rg, rr, ri, rz = fetch_galaxy_rotation_data(source_id)
            rotations = [rg, rr, ri, rz]

        for i, band in enumerate(data):
            if not data[i].any():
                st.write(f"No FITS data for band {'GRIZ'[i]}")
                continue

            with st.expander(f"FITS data for band {'GRIZ'[i]}:"):
                # Display rotation data if we've completed radon transform
                if rotations is not None:
                    st.write(f"Rotation: {rotations[i]}")

                fig, ax = plt.subplots()
                # v_min, v_max = np.percentile(data, (1, 99))
                ax.imshow(band, cmap="gray")  # vmin=v_min, vmax=v_max
                plt.axis("off")
                st.pyplot(fig)
else:
    st.write("No data")
