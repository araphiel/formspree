/** @format */

const formspree = window.formspree
const React = require('react')
const {Link} = require('react-router-dom')

import ajax from '../ajax'
import {LoadingContext, AccountContext} from '../Dashboard'
import Portal from '../Portal'
import {getProduct, addEmailAddress} from './utils'
import ActionInput from '../components/ActionInput'
import LoaderButton from '../components/LoaderButton'

class Account extends React.Component {
  constructor(props) {
    super(props)

    this.handleChangeNewAddress = this.handleChangeNewAddress.bind(this)
    this.handleAddEmail = this.handleAddEmail.bind(this)
    this.handleDeleteEmail = this.handleDeleteEmail.bind(this)

    this.state = {
      newAddress: '',
      newPending: []
    }
  }

  render() {
    let {user, sub, emails} = this.props
    let {newPending} = this.state
    let canAddEmails =
      user.features.unlimited_addresses ||
      emails.verified.length < formspree.LINKED_EMAIL_ADDRESSES_LIMIT
    return (
      <>
        <Portal to="#header .center">
          <h1>Your Account</h1>
        </Portal>
        <div className="container">
          <div className="col-1-2 wide-gutter">
            <p>
              You are registered with the email{' '}
              <span className="code">{user.email}</span> since{' '}
              {user.registered_on}.
            </p>
            <h3>Linked emails</h3>
            {user.features.unlimited_addresses ? null : (
              <p>
                {emails.verified.length} of{' '}
                {formspree.LINKED_EMAIL_ADDRESSES_LIMIT} email addresses added.
              </p>
            )}
            <form onSubmit={this.handleAddEmail}>
              <table className="emails">
                <tbody>
                  <ActionInput
                    rowOnly
                    name="address"
                    placeholder="Add an email to your account"
                    key={newPending.length}
                    disabled={!canAddEmails}
                    value={this.state.newAddress}
                    onChange={this.handleChangeNewAddress}
                  >
                    <LoaderButton
                      type="submit"
                      disabled={!canAddEmails || this.state.newAddress == ''}
                    >
                      Add
                    </LoaderButton>
                  </ActionInput>
                  {newPending.concat(emails.pending).map(email => (
                    <tr key={email} className="waiting_confirmation">
                      <td>
                        <a
                          className="delete"
                          href="#"
                          data-address={email}
                          onClick={this.handleDeleteEmail}
                        >
                          <i className="ion ion-trash-a delete" />
                        </a>
                        {email}
                      </td>
                      <td>
                        <span
                          className="tooltip hint--left"
                          data-hint="Please check your inbox."
                        >
                          <span className="status-indicator yellow" />
                        </span>
                      </td>
                    </tr>
                  ))}
                  {emails.verified.map(email => (
                    <tr key={email} className="verified">
                      <td>
                        <a
                          className="delete"
                          href="#"
                          data-address={email}
                          onClick={this.handleDeleteEmail}
                        >
                          <i className="ion ion-trash-a delete" />
                        </a>
                        {email}
                      </td>
                      <td>
                        <span
                          className="tooltip hint--left"
                          data-hint="Address verified."
                        >
                          <span className="status-indicator green" />
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </form>
          </div>
          <div className="col-1-2 wide-gutter">
            <PlanView user={user} sub={sub} />
          </div>
        </div>
      </>
    )
  }

  handleChangeNewAddress(e) {
    this.setState({newAddress: e.target.value})
  }

  async handleDeleteEmail(e) {
    e.preventDefault()

    let address = e.currentTarget.dataset.address

    await ajax({
      method: 'DELETE',
      endpoint: `/api-int/account/emails/${address}`,
      errorMsg: 'Failed to delete email address',
      successMsg: `${address} deleted successfully from your account.`,
      onSuccess: async r => {
        this.props.wait()
        await this.props.reloadAccount()
      }
    })

    this.props.ready()
  }

  async handleAddEmail(e) {
    e.preventDefault()

    await addEmailAddress(this.state.newAddress, {
      onSuccess: () => this.props.reloadAccount()
    })
    this.props.ready()
  }
}

const PlanView = ({user, sub}) => (
  <>
    <h3>Plan</h3>
    {user.features.dashboard ? (
      <>
        <p>
          You are a {formspree.SERVICE_NAME} {getProduct(user.product).name}{' '}
          user.
        </p>

        {sub &&
          (sub.cancel_at_period_end ? (
            <p>
              You've cancelled your subscription and it is ending on{' '}
              {sub.current_period_end}.
            </p>
          ) : (
            <p>
              Your subscription will automatically renew on{' '}
              {sub.current_period_end}.
            </p>
          ))}
        <div className="pad-top">
          <Link className="button" to="/account/billing">
            Manage Billing
          </Link>
        </div>
      </>
    ) : (
      <>
        Upgrade your account to gain access to
        <ol style={{textAlign: 'left'}}>
          <li>Unlimited submissions</li>
          <li>Access to submission archives</li>
          <li>
            Ability to hide your email from your page's HTML and replace it with
            a random-like URL
          </li>
          <li>Ability to submit AJAX forms</li>
          <li>Ability to create forms linked to other email accounts</li>
          <li>Custom email templates and "From" name</li>
        </ol>
        <Link className="button" to="/plans">
          Upgrade now
        </Link>
      </>
    )}
  </>
)

export default props => (
  <>
    <AccountContext.Consumer>
      {({user, sub, emails, reloadAccount}) => (
        <LoadingContext.Consumer>
          {({ready, wait}) => (
            <Account
              {...props}
              user={user}
              sub={sub}
              reloadAccount={reloadAccount}
              emails={emails}
              wait={wait}
              ready={ready}
            />
          )}
        </LoadingContext.Consumer>
      )}
    </AccountContext.Consumer>
  </>
)
