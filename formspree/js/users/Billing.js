/** @format */

const React = require('react')
import * as toast from '../toast'
const formspree = window.formspree
const {CardElement, Elements, injectStripe} = require('react-stripe-elements')
const {Link} = require('react-router-dom')

import {AccountContext, LoadingContext} from '../Dashboard'
import LoaderButton from '../components/LoaderButton'
import Portal from '../Portal'
import CancelModal from './CancelModal'
import Modal from '../components/Modal'
import Card from './Card'
import ajax from '../ajax'
import {getProduct} from './utils'

const MODAL_EDIT_INVOICE = 'MODAL_EDIT_INVOICE'
const MODAL_ADD_CARD = 'MODAL_ADD_CARD'
const MODAL_CANCEL = 'MODAL_CANCEL'

class Billing extends React.Component {
  constructor(props) {
    super(props)

    this.cardChanged = this.cardChanged.bind(this)
    this.addCard = this.addCard.bind(this)
    this.updateInvoiceAddress = this.updateInvoiceAddress.bind(this)
    this.closeModal = this.closeModal.bind(this)
    this.resubscribe = this.resubscribe.bind(this)
    this.toggleCardMenu = this.toggleCardMenu.bind(this)

    this.state = {
      modal: null,
      cardOpen: null
    }
  }

  cardChanged() {
    this.props.reloadAccount()
    this.closeModal()
  }

  renderCanceling(product, period_end) {
    return (
      <>
        <div className="container">
          <p>
            You are a {formspree.SERVICE_NAME} {product.name} user.
          </p>
          <p>
            You've cancelled your subscription and it is ending on {period_end}.
          </p>
        </div>

        <div className="container">
          <LoaderButton type="submit" onClick={this.resubscribe}>
            Resume Subscription
          </LoaderButton>
        </div>
        <div className="container">
          <a href="/plans" className="button">
            Change Plan
          </a>
        </div>
      </>
    )
  }

  renderSubscribed(product, period_end) {
    return (
      <>
        <div className="row spacer">
          <p>
            You are a {formspree.SERVICE_NAME} {product.name} user.
          </p>
          <p>Your subscription will automatically renew on {period_end}.</p>
        </div>

        <CancelModal
          sub={this.props.sub}
          isOpen={this.state.modal === MODAL_CANCEL}
          closing={this.closeModal}
        />

        <div className="row spacer">
          <button onClick={this.openModal(MODAL_CANCEL)}>
            Cancel Auto Renew
          </button>
        </div>
        <div className="row spacer">
          <Link className="button" to="/plans">
            Change Plan
          </Link>
        </div>
      </>
    )
  }

  toggleCardMenu(cardId) {
    this.setState({
      cardOpen: this.state.cardOpen === cardId ? null : cardId
    })
  }

  render() {
    let {user, sub, cards, invoices} = this.props
    const canceling = sub => sub && sub.cancel_at_period_end
    return (
      <>
        <Portal to="#header .center">
          <h1>Billing</h1>
        </Portal>
        <div className="container">
          <div className="col-1-2 wide-gutter">
            <h3>Plan</h3>
            {user.features.dashboard ? (
              canceling(sub) ? (
                this.renderCanceling(
                  getProduct(user.product),
                  sub.current_period_end
                )
              ) : (
                this.renderSubscribed(
                  getProduct(user.product),
                  sub.current_period_end
                )
              )
            ) : (
              <div className="container">
                <p>You don't have a plan yet. Click here to sign up!</p>
                <a href="/plans" className="button">
                  Choose Plan
                </a>
              </div>
            )}
          </div>

          <div className="col-1-2 wide-gutter">
            <h3>Wallet</h3>
            {sub &&
              (cards.length ? (
                <table id="card-list">
                  <tbody>
                    {cards.map(card => (
                      <Card
                        key={card.id}
                        onCardClicked={() => this.toggleCardMenu(card.id)}
                        card={card}
                        isOpen={this.state.cardOpen === card.id}
                        onCardChanged={this.props.reloadAccount}
                      />
                    ))}
                  </tbody>
                </table>
              ) : (
                <p>
                  We couldn't find any active cards in your wallet. Please make
                  sure to add a card by {sub.current_period_end} or your
                  subscription won't renew.
                </p>
              ))}

            <div className="row spacer">
              <Modal
                title="Add Card"
                isOpen={this.state.modal === MODAL_ADD_CARD}
                closing={this.closeModal}
                className="narrow"
              >
                <Elements>
                  <AddCardForm addCard={this.addCard} />
                </Elements>
              </Modal>

              <button onClick={this.openModal(MODAL_ADD_CARD)}>Add Card</button>
            </div>
          </div>
        </div>
        <div className="container spacer">
          <div className="col-1-1">
            <h3>Invoices</h3>
            <table id="invoices">
              <colgroup>
                <col width="27%" />
                <col width="35%" />
                <col width="10%" />
                <col width="10%" />
                <col width="18%" />
              </colgroup>
              <tbody>
                {invoices.map(
                  invoice =>
                    invoice.attempted ? (
                      <tr key={invoice.id}>
                        <td>{invoice.date}</td>
                        <td>{invoice.id}</td>
                        <td>${invoice.total / 100}</td>
                        <td>{invoice.paid ? 'Paid' : 'Unpaid'}</td>
                        <td>
                          <a
                            href={`/account/billing/invoice/${invoice.id.slice(
                              3
                            )}`}
                            className="button deemphasize"
                            target="_blank"
                          >
                            View Details
                          </a>
                        </td>
                      </tr>
                    ) : null
                )}
              </tbody>
            </table>
            <div className="row spacer">
              <button onClick={this.openModal(MODAL_EDIT_INVOICE)}>
                Edit invoice address
              </button>
              <Modal
                title="Edit Invoice Address"
                isOpen={this.state.modal === MODAL_EDIT_INVOICE}
                closing={this.closeModal}
                className="narrow"
              >
                <form onSubmit={this.updateInvoiceAddress}>
                  <textarea rows="4" name="invoice-address">
                    {user.invoice_address}
                  </textarea>
                  <LoaderButton className="submit card row spacer">
                    Update Invoice Address
                  </LoaderButton>
                </form>
              </Modal>
            </div>
          </div>
        </div>
      </>
    )
  }

  async resubscribe() {
    await ajax({
      endpoint: '/api-int/resubscribe',
      onSuccess: async () => {
        this.closeModal()

        this.props.wait()
        await this.props.reloadAccount()
      },
      errorMsg:
        'An error occurred and we were unable to resubscribe you. Please try ' +
        'again later or contact support for further assistance',
      successMsg: r => {
        return (
          'Glad to have you back! ' +
          `Your subscription will now automatically renew on ${r.at}`
        )
      }
    })

    this.props.ready()
  }

  async addCard(token) {
    await ajax({
      endpoint: '/api-int/account/cards',
      payload: {token: token.id},
      onSuccess: async () => {
        this.closeModal()

        this.props.wait()
        await this.props.reloadAccount()
      },
      errorMsg:
        'An error occurred and we were unable to add your card. Please ' +
        'try again later or contact support for further assistance',
      successMsg: 'New card added successfully.'
    })

    this.props.ready()
  }

  async updateInvoiceAddress(e) {
    e.preventDefault()

    let newaddr = e.target['invoice-address'].value

    await ajax({
      method: 'PATCH',
      endpoint: '/api-int/account',
      payload: {invoice_address: newaddr},
      onSuccess: () => {
        this.props.reloadAccount()
        this.closeModal()
      },
      errorMsg:
        'We were unable to change your invoice address. Please try again ' +
        'later or contact support for further assistance',
      successMsg: 'Invoice address changed.'
    })

    this.props.ready()
  }

  openModal(modalid) {
    return e => {
      e.preventDefault()
      this.setState({modal: modalid})
    }
  }

  closeModal(e) {
    if (e && e.preventDefault) e.preventDefault()
    this.setState({modal: null})
  }
}

const AddCardForm = injectStripe(
  class extends React.Component {
    constructor(props) {
      super(props)

      this.completeCheckout = this.completeCheckout.bind(this)
    }

    render() {
      return (
        <form onSubmit={this.completeCheckout} id="payment-form">
          <div className="input">
            <CardElement />
          </div>
          <div className="right">
            <p>Card data handled by Stripe</p>
          </div>
          <LoaderButton className="submit card row spacer">
            Add Card
          </LoaderButton>
        </form>
      )
    }

    async completeCheckout(e) {
      e.preventDefault()

      let {token, error} = await this.props.stripe.createToken()
      if (error) {
        toast.warning(error.message)
        return
      }

      this.props.addCard(token)
    }
  }
)

export default props => (
  <>
    <AccountContext.Consumer>
      {({user, sub, cards, invoices, reloadAccount}) => (
        <LoadingContext.Consumer>
          {({ready, wait}) => (
            <Billing
              {...props}
              user={user}
              sub={sub}
              cards={cards}
              invoices={invoices}
              reloadAccount={reloadAccount}
              ready={ready}
              wait={wait}
            />
          )}
        </LoadingContext.Consumer>
      )}
    </AccountContext.Consumer>
  </>
)
