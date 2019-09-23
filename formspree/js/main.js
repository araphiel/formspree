/**
 * @format
 */

import 'whatwg-fetch'
import * as toast from './toast'

/* turning flask flash messages into js popup notifications */
window.popupMessages.forEach(function(m, i) {
  var category = m[0] || 'info'
  var text = m[1]
  setTimeout(function() {
    toast[category](text)
  }, (1 + i) * 1500)
})

/* quick script for showing the resend confirmation form */
let resend = document.querySelector('a.resend')
if (resend) {
  resend.addEventListener('click', function(e) {
    e.preventDefault()

    resend.style.display = 'none'
    document.querySelector('form.resend').style.display = 'block'
  })
}

/* ------------------------------------------------------------------------- *
 * Menu Nav
 * ------------------------------------------------------------------------- */
;(function(window, document) {
  var OPEN_MENU_ID = 'open-hamburger'
  var CLOSE_MENU_ID = 'close-hamburger'
  var SHIM_ID = 'site-frame'
  var MENU_ID = 'account-nav'
  var EXPANDED_CLASS = 'expanded'

  function hasClass(el, name) {
    var re = new RegExp('(?:^|\\s)' + name + '(?!\\S)')
    return el.className.match(re)
  }

  function addClass(el, name) {
    el.className += ' ' + name
  }

  function removeClass(el, name) {
    var re = new RegExp('(?:^|\\s)' + name + '(?!\\S)', 'g')
    el.className = el.className.replace(re, '')
  }

  function toggleMenu(e) {
    e.preventDefault()
    var menu = document.getElementById(MENU_ID)
    if (hasClass(menu, EXPANDED_CLASS)) {
      removeClass(menu, EXPANDED_CLASS)
      document
        .getElementById(SHIM_ID)
        .removeEventListener('click', toggleMenu, true)
    } else {
      addClass(menu, EXPANDED_CLASS)
      document
        .getElementById(SHIM_ID)
        .addEventListener('click', toggleMenu, true)
    }
  }

  function bootstrap() {
    if (document.getElementById(OPEN_MENU_ID)) {
      document
        .getElementById(OPEN_MENU_ID)
        .addEventListener('click', toggleMenu)
      document
        .getElementById(CLOSE_MENU_ID)
        .addEventListener('click', toggleMenu)
    }
  }

  window.addEventListener('load', bootstrap)
})(window, document)

/* scripts at other files */
require('./react-app.js')
