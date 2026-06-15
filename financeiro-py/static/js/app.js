// Toggle formulários
function toggleForm(id) {
  const el = document.getElementById(id)
  if (!el) return
  const showing = el.style.display !== 'none'
  el.style.display = showing ? 'none' : 'block'
  if (!showing) {
    const first = el.querySelector('input:not([type=hidden]), select')
    if (first) first.focus()
  }
}

// Toggle form de salário
function toggleSalaryForm() {
  const display = document.getElementById('salary-display')
  const form = document.getElementById('salary-form')
  if (!display || !form) return
  const showing = form.style.display !== 'none'
  form.style.display = showing ? 'none' : 'block'
  display.style.display = showing ? 'block' : 'none'
  if (!showing) form.querySelector('input').focus()
}

// Checkbox de pagar — pega a data do input ao lado e submete
function submitPay(checkbox, billId) {
  if (!checkbox.checked) return
  const dateInput = document.getElementById('paid-at-' + billId)
  const hiddenInput = document.getElementById('paid-at-hidden-' + billId)
  const form = document.getElementById('pay-form-' + billId)
  if (hiddenInput && dateInput) hiddenInput.value = dateInput.value
  if (form) form.submit()
}

// Filtro de mês nas transações
function filtrarMes(val) {
  const [mes, ano] = val.split('/')
  const url = new URL(window.location.href)
  url.searchParams.set('mes', mes)
  url.searchParams.set('ano', ano)
  url.hash = 'transacoes'
  window.location.href = url.toString()
}

// Scroll suave ao carregar com hash
document.addEventListener('DOMContentLoaded', () => {
  const hash = window.location.hash
  if (hash) {
    const el = document.querySelector(hash)
    if (el) setTimeout(() => el.scrollIntoView({ behavior: 'smooth', block: 'start' }), 150)
  }

  // Remove flash automaticamente após 3s
  const flash = document.getElementById('flash-msg')
  if (flash) setTimeout(() => flash.remove(), 3000)
})
