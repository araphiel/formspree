/** @format */

const React = require('react')
const {Link} = require('react-router-dom')

import ajax from '../../ajax'
import {LoadingContext, AccountContext} from '../../Dashboard'
import LoaderButton from '../../components/LoaderButton'
import Switch from '../../components/Switch'
import DeleteSwitch from '../../components/DeleteSwitch'
import ActionInput from '../../components/ActionInput'

class FormSettings extends React.Component {
  constructor(props) {
    super(props)

    this.makeDirty = this.makeDirty.bind(this)
    this.isDirty = this.isDirty.bind(this)
    this.update = this.update.bind(this)
    this.resetAPIKey = this.resetAPIKey.bind(this)
    this.deleteForm = this.deleteForm.bind(this)

    this.state = {
      pendingChanges: {}
    }
  }

  render() {
    let {form, emails} = this.props
    let pending = this.state.pendingChanges
    const isSet = name => (name in pending ? pending[name] : form[name])

    let emailOptions = emails.verified.map(a => ({
      label: a + (form.hash ? ' (hard coded in the form action)' : ''),
      value: a
    }))

    if (!emailOptions.filter(e => e.value === form.email).length) {
      emailOptions.push({
        label: form.email + ' (unverified)',
        value: form.email,
        disabled: true
      })
    }

    return (
      <>
        <div className="container" id="settings">
          <form onSubmit={e => this.update()(e.target.name.value, 'name')}>
            <ActionInput
              name="name"
              label="Form Name"
              description="The form name won't be shown to your visitors."
              value={'name' in pending ? pending.name : form.name || ''}
              placeholder="No name set"
              onChange={this.makeDirty}
            >
              <LoaderButton disabled={!this.isDirty('name', form.name)}>
                Save
              </LoaderButton>
            </ActionInput>
          </form>
          <form onSubmit={e => this.update()(e.target.email.value, 'email')}>
            <ActionInput
              name="email"
              label="Target Email"
              description={
                <>
                  Where to send submissions. To add a new email address, visit
                  the <Link to="/account">account page</Link>.
                </>
              }
              value={pending.email || form.email || ''}
              placeholder="Target email address"
              onChange={this.makeDirty}
              options={emailOptions}
              disabled={form.hash || isSet('disable_email')}
            >
              {!form.hash && (
                <LoaderButton
                  disabled={
                    isSet('disable_email') || !this.isDirty('email', form.email)
                  }
                >
                  Save
                </LoaderButton>
              )}
            </ActionInput>
          </form>
          <Switch
            fieldName="disabled"
            description="Disable this form to stop receiving new
              submissions."
            onChange={this.update(true)}
            checked={!isSet('disabled')}
          >
            <h4>Form Enabled</h4>
          </Switch>
          <Switch
            fieldName="disable_email"
            description={
              form.routing_rules.length
                ? "You won't receive emails in the main address linked to this form because you have routing rules enabled. You can add a new rule with the condition 'true' to always receive the submissions at an specific address."
                : 'Enable or disable sending notification emails. Submissions will still be saved to the archive and dispatched to plugins.'
            }
            onChange={this.update(true)}
            checked={
              form.routing_rules.length ? false : !isSet('disable_email')
            }
            disabled={form.routing_rules.length}
          >
            <h4>Email Notifications</h4>
          </Switch>
          <Switch
            fieldName="disable_storage"
            description="Disable the submission archive if you don't want
              Formspree to store your submissions."
            onChange={this.update(true)}
            checked={!isSet('disable_storage')}
          >
            <h4>Submission Archive</h4>
          </Switch>
          <Switch
            fieldName="captcha_disabled"
            description="reCAPTCHA provides spam protection. Disabling it will remove the reCAPTCHA redirect."
            onChange={this.update(true)}
            checked={!isSet('captcha_disabled')}
          >
            <h4>reCAPTCHA</h4>
          </Switch>
          {form.features.api_access && (
            <>
              <Switch
                fieldName="api_enabled"
                description={
                  form.api_enabled
                    ? 'Disabling API access will wipe out the current API key.'
                    : "Allow programmatic access to this form's submissions."
                }
                onChange={this.update()}
                checked={isSet('api_enabled')}
              >
                <h4>HTTP API</h4>
              </Switch>
              {form.api_enabled && (
                <div className="row">
                  <div className="container">
                    <div id="apikey">
                      <div>
                        <div>
                          <span>Master API key:</span>
                          <span
                            className="code"
                            style={{margin: '10px', padding: '10px'}}
                          >
                            {form.apikey}
                          </span>
                        </div>
                        <div>
                          <span>Read-only API key:</span>
                          <span
                            className="code"
                            style={{margin: '10px', padding: '10px'}}
                          >
                            {form.apikey_readonly}
                          </span>
                        </div>
                      </div>
                      <div>
                        <LoaderButton onClick={this.resetAPIKey}>
                          Reset API key
                        </LoaderButton>
                      </div>
                    </div>
                  </div>
                </div>
              )}{' '}
            </>
          )}
          <DeleteSwitch
            description="Deleting the form will erase all traces of this form on our
              databases, including all the submissions."
            warningMessage={
              <>
                This will delete the form on <b>{form.host}</b> targeting{' '}
                <b>{form.email}</b> and all its submissions. This action{' '}
                <b>cannot</b> be undone.
              </>
            }
            onDelete={this.deleteForm}
          >
            <h4>Delete Form</h4>
          </DeleteSwitch>
        </div>
      </>
    )
  }

  makeDirty(e) {
    let {name, value} = e.target
    this.setState(state => {
      state.pendingChanges[name] = value
      return state
    })
  }

  isDirty(fieldName, lastValue) {
    return (
      fieldName in this.state.pendingChanges &&
      this.state.pendingChanges[fieldName] !== lastValue
    )
  }

  async updateFormName(e) {
    e.preventDefault()

    await this.update()('name', this.state.pendingChanges['name'])
    this.props.ready()
  }

  update(reversed = false) {
    return async (val, attr) => {
      this.setState(state => {
        state.pendingChanges[attr] = reversed ? !val : val
        return state
      })

      await ajax({
        method: 'PATCH',
        endpoint: `/api-int/forms/${this.props.form.hashid}`,
        payload: {
          [attr]: reversed ? !val : val
        },
        errorMsg: 'Failed to save settings',
        successMsg: 'Settings saved.',
        onSuccess: () => {
          this.props.reloadSpecificForm(this.props.form.hashid).then(() => {
            this.setState({pendingChanges: {}})
            this.props.ready()
          })
        }
      })
    }
  }

  async resetAPIKey(e) {
    e.preventDefault()

    this.setState(state => {
      state.pendingChanges.apikey = ''
      return state
    })

    await ajax({
      method: 'POST',
      endpoint: `/api-int/forms/${this.props.form.hashid}/reset-apikey`,
      errorMsg: 'Failed to reset API key',
      successMsg: 'A new API key was generated and replaced the old one.',
      onSuccess: async () => {
        return this.props.reloadSpecificForm(this.props.form.hashid)
      }
    })

    this.props.ready()
  }

  async deleteForm() {
    this.props.wait()

    await ajax({
      method: 'DELETE',
      endpoint: `/api-int/forms/${this.props.form.hashid}`,
      errorMsg: 'Failed to delete form',
      successMsg: 'Form successfully deleted.',
      onSuccess: async () => {
        this.props.history.push('/forms')

        this.props.wait()
        await this.props.reloadFormsList()
      }
    })

    this.props.ready()
  }
}

export default props => (
  <>
    <AccountContext.Consumer>
      {({forms, emails, reloadFormsList, reloadSpecificForm}) => (
        <LoadingContext.Consumer>
          {({ready, wait}) => (
            <FormSettings
              {...props}
              forms={forms}
              emails={emails}
              reloadFormsList={reloadFormsList}
              reloadSpecificForm={reloadSpecificForm}
              ready={ready}
              wait={wait}
            />
          )}
        </LoadingContext.Consumer>
      )}
    </AccountContext.Consumer>
  </>
)
