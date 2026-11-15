"""Send new, signed-out visitors to the landing page before the sign-in screen.

The landing page's buttons open the app with ``?from=site``, so anyone who has
already seen it goes straight to sign-in. Signed-in users never reach this.
"""
import json

import streamlit as st

from harnesssync.support_config import SITE_URL
from harnesssync.ui.language import tr

FROM_PARAM = "from"
FROM_SITE = "site"
_SEEN_KEY = "_seen_landing_page"
# Browser-side flag: this browser has been through the landing page before, so
# a bookmark of the bare app address goes straight to sign-in next time.
_BROWSER_KEY = "harnesssync-seen-landing"

_REMEMBER = (
    "<script>try { localStorage.setItem(%s, '1'); } catch (e) {}</script>"
    % json.dumps(_BROWSER_KEY)
)
_REDIRECT = """<script>
(function () {
  try {
    if (localStorage.getItem(%(key)s)) {
      var url = new URL(window.location.href);
      url.searchParams.set(%(param)s, %(value)s);
      window.location.replace(url.href);
      return;
    }
  } catch (e) {}
  window.location.replace(%(site)s);
})();
</script>""" % {"key": json.dumps(_BROWSER_KEY), "param": json.dumps(FROM_PARAM),
                "value": json.dumps(FROM_SITE), "site": json.dumps(SITE_URL)}


def came_from_site():
    # A gym flyer's QR (?gym=<slug>) is a deliberate way in, and the landing
    # page would drop the gym, so it counts as having come from the site.
    if st.query_params.get(FROM_PARAM) == FROM_SITE or _from_gym_flyer():
        st.session_state[_SEEN_KEY] = True
    return bool(st.session_state.get(_SEEN_KEY))


def _from_gym_flyer():
    slug = st.query_params.get("gym")
    if not slug or len(slug) > 40:
        return False
    from harnesssync import gym_report
    return gym_report.get_gym(slug) is not None


def _continue_to_sign_in():
    st.session_state[_SEEN_KEY] = True
    st.query_params[FROM_PARAM] = FROM_SITE


def send_new_visitors_to_landing():
    """Redirect to the landing page unless this visitor came from it.

    Call only for a signed-out visitor, just before the sign-in screen. The
    redirect is a browser-side ``location.replace``, so the Back button doesn't
    return to this placeholder. A browser that has been through the landing
    page before is sent on to sign-in instead. If scripts are blocked, the
    visitor sees links to the landing page and to sign-in.
    """
    if came_from_site():
        st.html(_REMEMBER, unsafe_allow_javascript=True)
        return
    st.html(_REDIRECT, unsafe_allow_javascript=True)
    st.title("🧗 HarnessSync")
    st.write(tr("Taking you to the HarnessSync home page…"))
    st.link_button(tr("Open the home page"), SITE_URL, type="primary")
    st.button(tr("I already have an account"), on_click=_continue_to_sign_in)
    st.stop()
