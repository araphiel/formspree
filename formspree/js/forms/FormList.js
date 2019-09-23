/** @format */

const React = require('react')
const {Link} = require('react-router-dom')

import {AccountContext} from '../Dashboard'
import CreateForm from './CreateForm'
import Portal from '../Portal'

class FormList extends React.Component {
  render() {
    let {user, forms} = this.props

    if (!user.features.dashboard) {
      return (
        <>
          <Portal to="#header .center">
            <h1>Your Forms</h1>
          </Portal>
          <div className="container">
            <div className="col-1-1">
              <p>
                Please <Link to="/account">upgrade your account</Link> in order
                to create forms from the dashboard and manage the forms
                currently associated with your emails.
              </p>
            </div>
          </div>
        </>
      )
    }

    return (
      <>
        <Portal to="#header .center">
          <h1>Your Forms</h1>
        </Portal>
        <div className="container">
          <div className="col-1-1">
            {forms.length ? (
              <table className="forms responsive">
                <thead>
                  <tr>
                    <th>Form Name</th>
                    <th>Count</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {forms.map(form => (
                    <FormItem key={form.hashid} {...form} />
                  ))}
                </tbody>
              </table>
            ) : (
              <p>
                You don't have any forms yet. Get started by clicking "Create
                Form".
              </p>
            )}
          </div>
        </div>
        <CreateForm user={user} {...this.props} />
      </>
    )
  }
}

class FormItem extends React.Component {
  render() {
    let form = this.props

    return (
      <tr>
        <td data-label="Form Name:">
          <Link to={`/forms/${form.hashid}/settings`} className="no-underline">
            {form.name ? (
              form.name
            ) : form.host ? (
              <div>
                {form.host}
                {form.sitewide ? (
                  <span
                    className="highlight tooltip hint--top"
                    data-hint="This form works for all paths under {{ form.host }}/"
                  >
                    {form.host.slice(-1)[0] === '/' ? '' : '/'} *
                  </span>
                ) : null}
              </div>
            ) : (
              'Waiting for a submission'
            )}
          </Link>
        </td>
        <td className="n-submissions" data-label="Submission Count:">
          {form.counter === 0 ? (
            <Link
              to={`/forms/${form.hashid}/integration`}
              className="no-underline"
            >
              <span className="never">never submitted</span>
            </Link>
          ) : (
            <Link
              to={`/forms/${form.hashid}/submissions`}
              className="no-underline"
            >
              {form.counter} submissions
            </Link>
          )}
        </td>
        <td data-label="Status:" className="right">
          {form.confirmed && !form.disabled ? (
            <>
              <span className="tooltip hint--left" data-hint="Active">
                <span className="status-indicator green" />
              </span>
              <span className="responsive-only">Active</span>
            </>
          ) : form.disabled ? (
            <>
              <span className="tooltip hint--left" data-hint="Disabled">
                <span className="status-indicator red" />
              </span>
              <span className="responsive-only">Disabled</span>
            </>
          ) : (
            <>
              <span
                className="tooltip hint--left"
                data-hint="Waiting for Activation"
              >
                <span className="status-indicator yellow" />
              </span>
              <span className="responsive-only">Waiting for Activation</span>
            </>
          )}
        </td>
      </tr>
    )
  }
}

export default props => (
  <>
    <AccountContext.Consumer>
      {({user, forms}) => <FormList {...props} user={user} forms={forms} />}
    </AccountContext.Consumer>
  </>
)
