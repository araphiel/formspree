/** @format */
const url = require('url')
const React = require('react')
const {withRouter} = require('react-router-dom')

export function logPageTransition(path) {
  let props,
    page,
    match = /\/forms\/(\w+)\/(\w+)/.exec(path)
  if (match) {
    page = 'Form Details'
    props = {form: match[1], tab: match[2]}
  } else {
    page = 'Page ' + path
  }
  amplitude.logEvent('Viewed ' + page, props)
}

class _PageTransition extends React.Component {
  componentDidUpdate(prevProps) {
    if (this.props.location !== prevProps.location) {
      window.scrollTo(0, 0)
      logPageTransition(this.props.location.pathname)
    }
  }

  render() {
    return this.props.children
  }
}

export const PageTransition = withRouter(_PageTransition)
