/** @format */

const React = require('react')
const {Route, NavLink, Redirect} = require('react-router-dom')

import Portal from '../../Portal'
import Integration from './Integration'
import Submissions from './Submissions'
import Settings from './Settings'
import Routing from './Routing'
import Whitelabel from './Whitelabel'
import Plugins from './Plugins'
import {AccountContext} from '../../Dashboard'

class FormPage extends React.Component {
  render() {
    let hashid = this.props.match.params.hashid

    var form
    for (let i = 0; i < this.props.forms.length; i++) {
      if (this.props.forms[i].hashid === hashid) {
        form = this.props.forms[i]
        break
      }
    }

    return (
      <>
        <Portal to="#header .center">
          <h1>Form Details</h1>
          {form && (
            <h2 className="form-description">
              for{' '}
              {form.name ? (
                form.name
              ) : (
                <>
                  <span className="code">
                    {!form.hash ? (
                      form.hashid
                    ) : form.host ? (
                      <>
                        {form.host}
                        {form.sitewide
                          ? form.host.slice(-1)[0] === '/'
                            ? '*'
                            : '/*'
                          : ''}
                      </>
                    ) : (
                      form.email
                    )}
                  </span>
                </>
              )}
            </h2>
          )}
        </Portal>
        <Route
          exact
          path={`/forms/${hashid}`}
          render={() => <Redirect to={`/forms/${hashid}/submissions`} />}
        />
        {form && (
          <div className="container">
            <div className="tabs row">
              <h4 className="col">
                <NavLink to={`/forms/${hashid}/integration`}>
                  Integration
                </NavLink>
              </h4>
              <h4 className="col">
                <NavLink to={`/forms/${hashid}/submissions`}>
                  Submissions
                </NavLink>
              </h4>
              <h4 className="col">
                <NavLink to={`/forms/${hashid}/settings`}>Settings</NavLink>
              </h4>
              <h4 className="col">
                <NavLink to={`/forms/${hashid}/plugins`}>Plugins</NavLink>
              </h4>
              {form.features.submission_routing && (
                <h4 className="col">
                  <NavLink to={`/forms/${hashid}/routing`}>Routing</NavLink>
                </h4>
              )}
              {form.features.whitelabel && (
                <h4 className="col">
                  <NavLink to={`/forms/${hashid}/whitelabel`}>
                    Whitelabel
                  </NavLink>
                </h4>
              )}
            </div>
            <Route
              path="/forms/:hashid/integration"
              render={() => <Integration form={form} />}
            />
            <Route
              path="/forms/:hashid/submissions"
              render={() => <Submissions form={form} />}
            />
            <Route
              path="/forms/:hashid/settings"
              render={() => (
                <Settings form={form} history={this.props.history} />
              )}
            />
            <Route
              path="/forms/:hashid/plugins"
              render={() => <Plugins form={form} />}
            />
            <Route
              path="/forms/:hashid/whitelabel"
              render={() => <Whitelabel form={form} />}
            />
            <Route
              path="/forms/:hashid/routing"
              render={() => <Routing form={form} />}
            />
          </div>
        )}
      </>
    )
  }
}

export default props => (
  <>
    <AccountContext.Consumer>
      {({forms}) => <FormPage {...props} forms={forms} />}
    </AccountContext.Consumer>
  </>
)
