/** @format */

const React = require('react')

import ajax from '../ajax'
import {AccountContext, LoadingContext} from '../Dashboard'
import LoaderButton from '../components/LoaderButton'
import Modal from '../components/Modal'

class CancelModal extends React.Component {
  constructor(props) {
    super(props)

    this.close = this.close.bind(this)
    this.cancelSubscription = this.cancelSubscription.bind(this)
  }

  render() {
    const {sub, ...props} = this.props

    return (
      <Modal {...props} title="Cancel Subscription">
        <form
          action="/api-int/cancel"
          method="POST"
          onSubmit={this.cancelSubscription}
        >
          <p>
            This will cancel your subscription at the end of your current
            billing cycle
            {sub ? ' on ' + sub.current_period_end : ''}. Your account will
            remain active until then.
          </p>
          <label>
            Why are you cancelling?
            <textarea
              name="why"
              placeholder="Was it a missing feature? Bad service? Just don't need us anymore?"
              required
            />
          </label>
          <div className="row spacer">
            <div className="col-1-2 left">
              <button onClick={this.close}>Don't Cancel</button>
            </div>
            <div className="col-1-2 right">
              <LoaderButton type="submit">Cancel Subscription</LoaderButton>
            </div>
          </div>
        </form>
      </Modal>
    )
  }

  async cancelSubscription(e) {
    e.preventDefault()

    let why = e.target['why'] && e.target['why'].value

    await ajax({
      endpoint: '/api-int/cancel',
      payload: {why},
      onSuccess: async () => {
        this.props.closing()

        this.props.wait()
        await this.props.reloadAccount()
      },
      errorMsg: 'Failed to cancel subscription.',
      successMsg: r => {
        return (
          'Subscription canceling. <br>' +
          `Your subscription will remain active until ${r.at}`
        )
      }
    })

    this.props.ready()
  }

  close(e) {
    e.preventDefault()
    this.props.closing()
  }
}

export default props => (
  <AccountContext.Consumer>
    {({reloadAccount}) => (
      <LoadingContext.Consumer>
        {({ready, wait}) => (
          <CancelModal
            {...props}
            ready={ready}
            wait={wait}
            reloadAccount={reloadAccount}
          />
        )}
      </LoadingContext.Consumer>
    )}
  </AccountContext.Consumer>
)
