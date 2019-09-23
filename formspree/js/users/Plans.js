/** @format */

import * as toast from '../toast'
const formspree = window.formspree
const React = require('react')
const {CardElement, Elements, injectStripe} = require('react-stripe-elements')
const md5 = require('js-md5')

import {LoadingContext, AccountContext} from '../Dashboard'
import Modal from '../components/Modal'
import CancelModal from './CancelModal'
import Portal from '../Portal'
import LoaderButton from '../components/LoaderButton'
import {getProduct, deepCopy} from './utils'
import ajax from '../ajax'

const STEP_CANCEL = -1
const STEP_NOTHING = 0
const STEP_REGISTER = 1
const STEP_PERSONAL = 2
const STEP_PAYMENT = 3

const INITIAL_STATE = {
  step: STEP_NOTHING,
  modalOpened: null,
  data: {
    productId: null, // this is the product id, ie. "gold" or "platinum"
    stripePlan: null, // this is the plan in Stripe, ie "v1_gold_yearly"
    email: '',
    password: '',
    passwordcheck: '',
    name: '',
    address: '',
    country: 'US',
    zip: '',
    coupon: '',
    token: null,
    why: ''
  }
}

class Plans extends React.Component {
  constructor(props) {
    super(props)

    this.makeSelectFn = this.makeSelectFn.bind(this)
    this.setData = this.setData.bind(this)
    this.prev = this.prev.bind(this)
    this.next = this.next.bind(this)
    this.resubscribe = this.resubscribe.bind(this)
    this.closeModal = this.closeModal.bind(this)

    this.products = window.formspree.products
    this.state = deepCopy(INITIAL_STATE)
  }

  productRenderer() {
    let lastFeature = 0

    return (prod, current, canceling) => {
      let featureCount = 0

      let buttonClass = 'product-button emphasize'
      let buttonDisabled =
        prod.id === 'free' ? current || canceling : current && !canceling
      let buttonAction =
        current && canceling ? this.resubscribe : this.makeSelectFn(prod.id)

      return (
        <div className="col-1-3" key={prod.id}>
          <h1 className="center">{prod.name}</h1>
          <h3 className="center">{prod.description}</h3>
          <ul className="product-list center">
            {prod.monthly.features.map(feat => {
              featureCount++
              let result = (
                <li
                  className={featureCount <= lastFeature ? 'redundant' : ''}
                  key={feat.name}
                >
                  {feat.name}
                </li>
              )
              lastFeature = Math.max(featureCount, lastFeature)
              return result
            })}
          </ul>
          <h3 className="center">
            ${(prod.yearly && prod.yearly.price / 12) || prod.monthly.price} /mo
            {prod.yearly && <div className="small center">billed annually</div>}
          </h3>{' '}
          {/*
          {prod.yearly ? (
            <>
              <h3 className="center">
                HOLIDAY SALE! <br />
                {'$' + prod.yearly.price / 24 + ' /mo'}
              </h3>
              <h4 className="center small">
                first year then {'$' + prod.yearly.price / 12 + ' /mo'}
                <br />
                billed annually
              </h4>
            </>
          ) : (
            ''
          )}
          */}
          <h4 className="center small">
            {prod.yearly && 'or $' + prod.monthly.price + ' billed monthly'}
          </h4>
          {prod.id !== 'free' && this.renderAccountModal(prod.id)}
          {prod.id !== 'free' && this.renderBillingModal(prod.id)}
          {prod.id !== 'free' && this.renderPurchaseModal(prod.id)}
          {this.props.user &&
            prod.id === 'free' &&
            this.renderCancelModal(prod.id)}
          <div className="center">
            {current && canceling ? (
              <LoaderButton
                className={buttonClass}
                onClick={buttonAction}
                disabled={buttonDisabled}
              >
                Resume
              </LoaderButton>
            ) : (
              <button
                className={buttonClass}
                onClick={buttonAction}
                disabled={buttonDisabled}
              >
                {current && !canceling
                  ? 'Current'
                  : canceling && prod.id === 'free'
                    ? 'Canceling'
                    : 'Select'}
              </button>
            )}
          </div>
        </div>
      )
    }
  }

  renderAccountModal(productId) {
    let {data, step, modalOpened} = this.state
    return (
      <Modal
        title={`Account Details`}
        isOpen={modalOpened === productId && step === STEP_REGISTER}
        closing={this.closeModal}
        className="narrow"
      >
        <div>
          <div>
            <form onSubmit={this.next}>
              <label>
                Email:{' '}
                <input
                  type="email"
                  autoComplete="email"
                  name="email"
                  required
                  autoFocus
                  value={data.email}
                  onChange={this.setData('email')}
                />
              </label>
              <label>
                Password:{' '}
                <input
                  type="password"
                  required
                  value={data.password}
                  onChange={this.setData('password')}
                />
              </label>
              <label>
                Password (again):{' '}
                <input
                  type="password"
                  required
                  value={data.passwordcheck}
                  onChange={this.setData('passwordcheck')}
                />
              </label>
              <div className="row right spacer">
                <button>Next &gt;</button>
              </div>
            </form>
          </div>
        </div>
      </Modal>
    )
  }

  renderBillingModal(productId) {
    let {data, step, modalOpened} = this.state
    return (
      <Modal
        title={
          <h4>
            {!this.props.user && (
              <button className="inline" onClick={this.prev}>
                &lt; Back &nbsp;&nbsp;&nbsp;
              </button>
            )}
            Billing Address
          </h4>
        }
        isOpen={modalOpened === productId && step === STEP_PERSONAL}
        closing={this.closeModal}
        className="narrow"
      >
        <div>
          <div>
            <form onSubmit={this.next}>
              <label>
                Name:{' '}
                <input
                  autoComplete="name"
                  name="name"
                  autoFocus
                  required
                  value={data.name}
                  onChange={this.setData('name')}
                />
              </label>
              <label>
                Address:{' '}
                <input
                  autoComplete="street-address"
                  name="street-address"
                  required
                  value={data.address}
                  onChange={this.setData('address')}
                />
              </label>
              <div className="row">
                <label className="col-1-2">
                  Postal Code:{' '}
                  <input
                    autoComplete="postal-code"
                    name="postal-code"
                    required
                    value={data.zip}
                    onChange={this.setData('zip')}
                  />
                </label>
                <label className="col-1-2">
                  Country:{' '}
                  <div className="row">
                    <div className="col-1-2">
                      <select
                        required
                        value={data.country}
                        onChange={this.setData('country')}
                      >
                        {formspree.countries.sort().map(c => (
                          <option value={c} key={c}>
                            {c}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div
                      className="flag-input col-1-2"
                      style={{
                        backgroundImage:
                          'url(' +
                          `/static/img/countries/${data.country.toLowerCase()}.png` +
                          ')'
                      }}
                    >
                      <input type="text" disabled />
                    </div>
                  </div>
                </label>
              </div>
              <div className="row right spacer">
                <button>Next &gt;</button>
              </div>
            </form>
          </div>
        </div>
      </Modal>
    )
  }

  renderPurchaseModal(productId) {
    let {data, step, modalOpened} = this.state
    return (
      <Modal
        title={
          <h4>
            {!this.props.user && (
              <button className="inline" onClick={this.prev}>
                &lt; Back &nbsp;&nbsp;&nbsp;
              </button>
            )}
            Purchase {formspree.SERVICE_NAME} {getProduct(productId).name}
          </h4>
        }
        isOpen={modalOpened === productId && step === STEP_PAYMENT}
        closing={this.closeModal}
        className="narrow"
      >
        <Elements>
          <PaymentForm
            userHasSubAlreadySoDontAsk={this.props.user && this.props.sub}
            data={data}
            product={getProduct(productId)}
            setData={this.setData}
            prev={this.prev}
            next={this.next}
            ready={this.props.ready}
          />
        </Elements>
      </Modal>
    )
  }

  renderCancelModal(productId) {
    let {step, modalOpened} = this.state
    return (
      <CancelModal
        sub={this.props.sub}
        isOpen={modalOpened === productId && step === STEP_CANCEL}
        closing={this.closeModal}
      />
    )
  }

  render() {
    let {user, sub} = this.props
    const renderProduct = this.productRenderer()
    const planInProduct = (plan_id, prod) =>
      -1 !==
      [prod.monthly, prod.yearly]
        .filter(x => x)
        .map(x => x.stripe_plan)
        .indexOf(plan_id)
    const isCurrent = (prod, user) =>
      (user && planInProduct(user.plan, prod)) || (!user && 'free' === prod.id)
    const isCanceling = sub && sub.cancel_at_period_end
    const isLegacyPlan =
      user &&
      0 === this.products.filter(prod => planInProduct(user.plan, prod)).length
    return (
      <>
        <Portal to="#header .center">
          <h1>Formspree Plans</h1>
        </Portal>
        <div className="container">
          {isLegacyPlan ? (
            <div className="container center">
              <h3>You're in a legacy plan.</h3>
            </div>
          ) : null}
          <div className="row" id="plans">
            {this.products.map(prod =>
              renderProduct(prod, isCurrent(prod, user), isCanceling)
            )}
          </div>
        </div>
      </>
    )
  }

  closeModal(e) {
    e && e.preventDefault()
    this.setState(deepCopy(INITIAL_STATE))
  }

  makeSelectFn(productId) {
    return e => {
      e.preventDefault()

      this.setState(state => {
        state.modalOpened = productId
        state.data.productId = productId

        if (productId === 'free') {
          state.step = STEP_CANCEL
        } else if (this.props.user && this.props.sub) {
          state.step = STEP_PAYMENT
        } else if (this.props.user) {
          state.step = STEP_PERSONAL
        } else {
          state.step = STEP_REGISTER
        }

        return state
      })
    }
  }

  async resubscribe() {
    await ajax({
      endpoint: '/api-int/resubscribe',
      onSuccess: async () => {
        this.closeModal()

        this.props.wait()
        await this.props.reloadAccount()
      },
      errorMsg: 'Failed to resubscribe',
      successMsg: r => {
        return (
          'Glad to have you back! ' +
          `Your subscription will now automatically renew on ${r.at}`
        )
      }
    })

    this.props.ready()
  }

  async next(e) {
    e.preventDefault()
    let {data, step} = this.state

    var valid = true
    function check(fieldName) {
      if (!data[fieldName]) {
        toast.warning(`Missing field "${fieldName}".`)
        valid = false
      }
    }

    switch (step) {
      case STEP_REGISTER:
        ;['email', 'password'].forEach(check)

        if (data.password !== data.passwordcheck) {
          toast.warning(`Passwords don't match.`)
          valid = false
        }

        if (valid) {
          amplitude.logEvent('Clicked Checkout Next', {step: 'register'})
          this.setState({step: this.state.step + 1})
        }
        break
      case STEP_PERSONAL:
        ;['name', 'address', 'country', 'zip'].forEach(check)

        if (valid) {
          amplitude.logEvent('Clicked Checkout Next', {step: 'personal'})
          this.setState({step: this.state.step + 1})
        }
        break
      case STEP_PAYMENT:
        // at this point we should have a stripe token already
        // so we proceed to register/upgrade
        let payload = {
          plan: data.stripePlan,
          token: data.token,
          coupon: data.coupon
        }

        if (data.email && data.password) {
          payload.email = data.email
          payload.password = data.password
        }

        amplitude.logEvent('Clicked Checkout Next', {step: 'payment'})

        await ajax({
          method: 'POST',
          endpoint: '/api-int/buy',
          payload,
          onSuccess: async () => {
            amplitude.logEvent('Subscribed')

            this.closeModal()

            this.props.wait()
            await this.props.reloadAccount()
            if (!this.props.user) {
              this.props.history.push('/dashboard')
            }
          },
          errorMsg: 'Failed to create a subscription',
          successMsg: 'Subscription created!'
        })

        this.props.ready()
        break
    }
  }

  prev(e) {
    e.preventDefault()
    this.setState({step: this.state.step - 1})
  }

  setData(key, value) {
    // either immediately sets a value, or returns a function
    // that can be used to set the value later
    const setState = value => {
      this.setState(state => {
        state.data[key] = value
        return state
      })
    }
    if (value !== undefined) {
      setState(value)
      return
    }
    return e => {
      let value = e.target.value
      setState(value)
    }
  }
}

const PaymentForm = injectStripe(
  class extends React.Component {
    constructor(props) {
      super(props)
      this.props.setData('stripePlan', this.props.product.yearly.stripe_plan)
      this.completeCheckout = this.completeCheckout.bind(this)
    }

    render() {
      let {data, setData, userHasSubAlreadySoDontAsk} = this.props
      let {monthly: m, yearly: y} = this.props.product

      const getTotal = () =>
        data.stripePlan === y.stripe_plan ? y.price : m.price

      let couponProps = getCouponProps(data.coupon)

      return (
        <div>
          <form onSubmit={this.completeCheckout}>
            {/*<div>
               <label>
                 Coupon code:{' '}
                 <input
                   name="coupon"
                   onChange={setData('coupon')}
                   value={data.coupon}
                 />
               </label>
             </div>*/}
            {couponProps.no_card ? (
              <p>You won't be charged.</p>
            ) : (
              <>
                <div>
                  <label className="plan-select">
                    <input
                      type="radio"
                      name="stripePlan"
                      checked={data.stripePlan === y.stripe_plan}
                      onChange={setData('stripePlan')}
                      value={y.stripe_plan}
                      required
                    />{' '}
                    Yearly Billing ${(y.price / 12).toFixed(0)}
                    /mo ($
                    {y.price} total, ${(m.price * 12 - y.price).toFixed(0)}{' '}
                    discount) {/*Yearly Billing ${(y.price / 24).toFixed(0)}*/}
                    {/*/mo first year then ${(y.price / 12).toFixed(0)} /mo <br />(*/}
                    {/*<span class="emphasize">HOLIDAY SALE!</span> $*/}
                    {/*{(y.price / 2).toFixed(0)} discount)*/}
                    {/*<br />{' '}*/}
                  </label>
                </div>
                <div>
                  <label className="plan-select">
                    <input
                      type="radio"
                      name="stripePlan"
                      checked={data.stripePlan === m.stripe_plan}
                      onChange={setData('stripePlan')}
                      value={m.stripe_plan}
                      required
                    />{' '}
                    Monthly Billing ${m.price}
                    /mo
                  </label>
                </div>
                {userHasSubAlreadySoDontAsk ? (
                  <p>Your card on file will be charged.</p>
                ) : (
                  <>
                    <p>Total amount to be charged today: ${getTotal()}</p>
                    <div className="input">
                      <CardElement
                        hidePostalCode
                        ref={instance => {
                          if (instance) {
                            instance._element.once('ready', () => {
                              instance._element.focus()
                            })
                          }
                        }}
                      />
                    </div>
                    <div className="right">
                      <p>Payment handled by Stripe</p>
                    </div>
                  </>
                )}
              </>
            )}
            <LoaderButton className="row spacer">Purchase</LoaderButton>
          </form>
        </div>
      )
    }

    async completeCheckout(e) {
      e.preventDefault()

      let {data} = this.props

      let couponProps = getCouponProps(data.coupon)

      if (couponProps.force_plan) {
        data.plan = couponProps.force_plan
      }

      if (!couponProps.no_card && !this.props.userHasSubAlreadySoDontAsk) {
        let {token, error} = await this.props.stripe.createToken({
          name: data.name,
          address_line1: data.address,
          address_country: data.country,
          address_zip: data.zip
        })

        if (error) {
          toast.warning(error.message)
          this.props.ready()
          return
        }
        this.props.setData('token')({target: {value: token.id}})
      }

      this.props.next({preventDefault() {}})
    }
  }
)

function getCouponProps(coupon) {
  let hcoupon = coupon && md5(coupon.toLowerCase())
  return hcoupon in formspree.coupons ? formspree.coupons[hcoupon] : {}
}

export default props => (
  <>
    <AccountContext.Consumer>
      {({sub, user, reloadAccount}) => (
        <LoadingContext.Consumer>
          {({ready, wait}) => (
            <Plans
              {...props}
              sub={sub}
              user={user}
              reloadAccount={reloadAccount}
              wait={wait}
              ready={ready}
            />
          )}
        </LoadingContext.Consumer>
      )}
    </AccountContext.Consumer>
  </>
)
