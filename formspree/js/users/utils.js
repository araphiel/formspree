/** @format */

import * as toast from '../toast'
const isValidEmail = require('is-valid-email')

import ajax from '../ajax'

export function getProduct(id) {
  const products = window.formspree.products.filter(prod => prod.id === id)
  return products.length > 0 ? products[0] : undefined
}

export function deepCopy(obj) {
  return JSON.parse(JSON.stringify(obj))
}

export async function addEmailAddress(address, params) {
  if (!isValidEmail(address)) {
    toast.warning(`"${address}" is not a valid email address.`)
    return new Promise(resolve => setTimeout(resolve, 1))
  }

  await ajax({
    method: 'POST',
    endpoint: '/api-int/account/emails',
    payload: {address},
    errorMsg: 'Failed add email to your account',
    successMsg: r => r.message,
    onSuccess: async r => {
      if (!r.noop) {
        await params.onSuccess(r)
      }
    }
  })
}
