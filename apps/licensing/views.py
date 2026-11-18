from django import forms
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from .middleware import MESSAGES
from .services import LicenseError, activate


class ActivationForm(forms.Form):
    code = forms.CharField(max_length=256, strip=False, widget=forms.PasswordInput)
    next = forms.CharField(required=False, widget=forms.HiddenInput)


@require_http_methods(["GET", "POST"])
@csrf_protect
def activation(request):
    form = ActivationForm(request.POST or None, initial={"next": request.GET.get("next", "/")})
    error = None
    if request.method == "POST" and form.is_valid():
        try:
            activate(form.cleaned_data["code"])
            target = form.cleaned_data["next"]
            if not url_has_allowed_host_and_scheme(
                target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
            ):
                target = "/"
            return HttpResponseRedirect(target or "/")
        except LicenseError as exc:
            error = MESSAGES.get(exc.code, "授权不可用，请联系售后。")
    return render(
        request,
        "licensing/activation.html",
        {"form": form, "error": error},
        status=403 if error else 200,
    )
