/** @format */

const React = require('react')
const {findDOMNode} = require('react-dom')

import {LoadingContext} from '../Dashboard'

class LoaderButton extends React.Component {
  constructor(props) {
    super(props)

    this.id = parseInt(Math.random() * 100000)

    this.startWaiting = this.startWaiting.bind(this)
  }

  componentDidMount() {
    this.button = findDOMNode(this)

    if (this.props.onClick) {
      // the presence of an onClick for our purposes disqualifies
      // this form as a form-submit trigger, it is instead just
      // a rogue button and his independent onClick behavior.
      this.button.addEventListener('click', this.startWaiting)
      this.button.addEventListener('click', this.props.onClick)
    } else {
      // if there's no onClick it means the button is submitting
      // a form that is his ancestor.

      var parentForm = this.button.parentNode
      for (let i = 0; i < 6; i++) {
        if (parentForm.tagName === 'FORM') {
          break
        }
        parentForm = parentForm.parentNode
      }

      if (parentForm.tagName === 'FORM') {
        this.parentForm = parentForm
        this.parentForm.addEventListener('submit', this.startWaiting)
      }
    }
  }

  componentWillUnmount() {
    let attached = this.parentForm || this.button
    attached.removeEventListener('submit', this.startWaiting)
  }

  render() {
    var props = {...this.props}
    delete props.waitButton
    delete props.waitingButton
    delete props.children
    delete props.onClick

    let loading = this.props.waitingButton === this.id
    if (loading) {
      props.disabled = true
    }

    props.className =
      (props.className || '') + ' loader-button' + (loading ? ' loading' : '')

    return <button {...props}>{this.props.children}</button>
  }

  startWaiting(e) {
    e.preventDefault()
    this.props.waitButton(this.id)
  }
}

export default props => (
  <LoadingContext.Consumer>
    {({waitButton, waitingButton}) => (
      <LoaderButton
        {...props}
        waitButton={waitButton}
        waitingButton={waitingButton}
      />
    )}
  </LoadingContext.Consumer>
)
