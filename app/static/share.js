// « Copier le lien » d'un projet public ; si la copie échoue, l'adresse s'affiche pour la copier à la main.
document.querySelector("[data-copy]").addEventListener("click", ({currentTarget: button}) => {
  const copied = navigator.clipboard ? navigator.clipboard.writeText(button.dataset.copy) : Promise.reject();
  copied.then(() => { button.lastChild.textContent = " Lien copié"; }, () => button.insertAdjacentText("afterend", " " + button.dataset.copy));
});
