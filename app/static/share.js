// « Copier le lien » d'un projet public ; si la copie échoue, l'adresse s'affiche pour la copier à la main.
document.querySelector("[data-copy]").addEventListener("click", ({target}) => {
  const copied = navigator.clipboard ? navigator.clipboard.writeText(target.dataset.copy) : Promise.reject();
  copied.then(() => { target.textContent = "Lien copié"; }, () => target.insertAdjacentText("afterend", " " + target.dataset.copy));
});
