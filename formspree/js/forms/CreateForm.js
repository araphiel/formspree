/** @format */

import * as toast from '../toast'
const React = require('react')
const {Link} = require('react-router-dom')

import Modal from '../components/Modal'
import ajax from '../ajax'
import LoaderButton from '../components/LoaderButton'
import {LoadingContext, AccountContext} from '../Dashboard'

class CreateForm extends React.Component {
  constructor(props) {
    super(props)

    this.openModal = this.openModal.bind(this)
    this.closeModal = this.closeModal.bind(this)
    this.create = this.create.bind(this)

    this.state = {
      modalOpened: false,
      selectLoading: false,
      name: 'A new form'
    }
  }

  static getDerivedStateFromProps(props, state) {
    // when user has loaded, update internal state
    if (props.user !== undefined && state.email === undefined) {
      let owner = props.user.email
      let verified = props.emails.verified
      state.email =
        (verified.includes(owner) && owner) ||
        (verified.length > 0 && verified[0])
    }
    return state
  }

  renderOptions() {
    return (
      <>
        {this.props.emails.verified
          .map(addr => (
            <option key={addr} value={addr}>
              {addr}
            </option>
          ))
          .concat(
            this.props.emails.pending.map(addr => (
              <option key={addr} value={addr} disabled>
                {addr} (pending verification)
              </option>
            ))
          )}
      </>
    )
  }

  renderModal() {
    return (
      <Modal
        isOpen={this.state.modalOpened}
        closing={this.closeModal}
        className="narrow"
        title="Create form"
      >
        {this.props.emails.verified.length < 1 ? (
          <>
            <h4 className="center">You have no verified email addresses.</h4>
            <div className="center">
              Please check your inbox for the verification email. You can also
              link additional email addresses on the{' '}
              <Link to="/account">account page</Link>.
            </div>
            <div className="row spacer right">
              <button className="deemphasize" onClick={this.closeModal}>
                OK
              </button>
            </div>
          </>
        ) : (
          <form onSubmit={this.create}>
            <label>
              Form name:
              <input
                type="name"
                value={this.state.name}
                onChange={e => this.setState({name: e.target.value})}
                placeholder="Your form must have a name."
                required
              />
            </label>
            <label className="row spacer">
              Send emails to:
              <div className="select">
                <select
                  value={this.state.email}
                  onChange={e => this.setState({email: e.target.value})}
                  required
                >
                  {this.renderOptions()}
                </select>
              </div>
            </label>
            <div>
              To send to a different email address, please add a Linked Email on
              the <Link to="/account">account page</Link>.
            </div>
            <div className="row spacer">
              <div className="create-button right">
                <LoaderButton type="submit">Create form</LoaderButton>
              </div>
            </div>
          </form>
        )}
      </Modal>
    )
  }

  render() {
    return (
      <div className="create-form container">
        {this.renderModal()}
        <a href="#" onClick={this.openModal} className="button emphasize">
          Create a form
        </a>
      </div>
    )
  }

  async create(e) {
    let {name, email} = this.state

    e.preventDefault()

    await ajax({
      endpoint: '/api-int/forms',
      method: 'POST',
      payload: {name, email},
      errorMsg: 'Error creating form',
      successMsg: 'Form created!',
      onSuccess: r => {
        this.props.reloadSpecificForm(r.hashid)
        this.props.history.push(`/forms/${r.hashid}/integration`)
      }
    })

    this.props.ready()
  }

  openModal(e) {
    e.preventDefault()
    this.setState({modalOpened: true})
  }

  closeModal(e) {
    e && e.preventDefault()
    this.setState({modalOpened: false})
  }
}

export default props => (
  <>
    <AccountContext.Consumer>
      {({emails, user, reloadAccount, reloadSpecificForm}) => (
        <LoadingContext.Consumer>
          {({ready}) => (
            <CreateForm
              {...props}
              user={user}
              emails={emails}
              reloadAccount={reloadAccount}
              reloadSpecificForm={reloadSpecificForm}
              ready={ready}
            />
          )}
        </LoadingContext.Consumer>
      )}
    </AccountContext.Consumer>
  </>
)
