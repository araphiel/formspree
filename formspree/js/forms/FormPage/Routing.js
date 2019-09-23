/** @format */

import get from 'lodash.get'
import set from 'lodash.set'
import cloneDeep from 'lodash.clonedeep'

const cs = require('class-set')
const React = require('react')
const {Link} = require('react-router-dom')

import ajax from '../../ajax'
import {LoadingContext, AccountContext} from '../../Dashboard'
import LoaderButton from '../../components/LoaderButton'
import ActionInput from '../../components/ActionInput'

class FormRoutingRules extends React.Component {
  constructor(props) {
    super(props)

    this.newRule = this.newRule.bind(this)
    this.saveRule = this.saveRule.bind(this)
    this.deleteRule = this.deleteRule.bind(this)
    this.changeRule = this.changeRule.bind(this)
    this.listAllRules = this.listAllRules.bind(this)

    this.state = {
      fields: [],
      pendingRules: []
    }

    this.blankRule = {
      dirty: true,
      email: this.props.emails.verified[0],
      trigger: {fn: 'true', field: null, params: []}
    }
  }

  async componentDidMount() {
    await ajax({
      method: 'GET',
      endpoint: `/api-int/forms/${this.props.form.hashid}/fields`,
      onSuccess: fields => {
        this.setState({fields})
      }
    })
  }

  render() {
    if (this.state.fields.length === 0) {
      return (
        <div id="routing_rules">
          <div className="row">
            <p>
              This form doesn't have any submissions. Please make a test
              submission first so we'll have a sample of field names to be used
              while building the rules.
            </p>
          </div>
        </div>
      )
    }

    if (this.props.emails.verified.length === 0) {
      return (
        <div id="routing_rules">
          <div className="row">
            <p>
              You don't have any verified emails in your account. Go to the
              <Link to="/account">account page</Link> to add some.
            </p>
          </div>
          <div className="row spacer">
            <button onClick={this.newRule}>Add Rule</button>
          </div>{' '}
        </div>
      )
    }

    if (this.listAllRules().length === 0) {
      return (
        <div id="routing_rules">
          <div className="row">
            <p>
              There are no rules defined. Click <code>Add Rule</code> below to
              add some.
            </p>
          </div>
          <div className="row spacer">
            <button onClick={this.newRule}>Add Rule</button>
          </div>{' '}
          <div
            className="row spacer col-1-2 disabled"
            style={{fontSize: 'small'}}
          >
            If no rules are defined, submissions will be sent to the form's
            target email address ({this.props.form.email}
            ), unless disabled in the form's settings.
          </div>{' '}
        </div>
      )
    }

    return (
      <>
        <div id="routing_rules">
          <div className="row">
            <table>
              <thead style={{tableLayout: 'fixed'}}>
                <tr>
                  <th style={{width: '25%'}}>Target Email</th>
                  <th style={{width: '75%'}}>Condition</th>
                </tr>
              </thead>
              <tbody>
                {this.listAllRules().map(rule => (
                  <ActionInput
                    key={rule.id}
                    rowOnly={true}
                    className="email"
                    label="Target Email"
                    value={rule.email}
                    placeholder="Target email address"
                    onChange={e =>
                      this.changeRule('email', rule.id, e.target.value)
                    }
                    options={this.props.emails.verified.map(email => ({
                      value: email,
                      label: email
                    }))}
                  >
                    <div className="rule">
                      <select
                        value={rule.trigger.fn}
                        className="rule-part"
                        onChange={e =>
                          this.changeRule('trigger.fn', rule.id, e.target.value)
                        }
                      >
                        {window.formspree.rule_fns.map(fn => (
                          <option value={fn.name} key={fn.name}>
                            {fn.doc}
                          </option>
                        ))}
                      </select>
                      {this.getFunction(rule.trigger.fn).uses_field && (
                        <select
                          value={rule.trigger.field || ''}
                          className="rule-part"
                          onChange={e =>
                            this.changeRule(
                              'trigger.field',
                              rule.id,
                              e.target.value
                            )
                          }
                        >
                          <option value="" key={'-1'}>
                            Select a field:
                          </option>{' '}
                          {this.state.fields
                            .filter(f => f[0] !== '_')
                            .map(f => (
                              <option value={f} key={f}>
                                {f} field
                              </option>
                            ))}
                        </select>
                      )}
                      {this.getFunction(rule.trigger.fn).params.map(
                        (pname, pidx) => (
                          <input
                            value={rule.trigger.params[pidx] || ''}
                            className="rule-part"
                            placeholder="string to match"
                            onChange={e =>
                              this.changeRule(
                                `trigger.params.${pidx}`,
                                rule.id,
                                e.target.value
                              )
                            }
                          />
                        )
                      )}
                      <LoaderButton
                        className="rule-button"
                        disabled={!rule.dirty || !this.validRule(rule)}
                        onClick={e => this.saveRule(e, rule.id)}
                      >
                        Save
                      </LoaderButton>
                      <LoaderButton
                        className="rule-button emphasize"
                        disabled={this.idIsTemporary(rule.id)}
                        onClick={e => this.deleteRule(e, rule.id)}
                      >
                        Delete
                      </LoaderButton>
                    </div>
                  </ActionInput>
                ))}
              </tbody>
            </table>

            <div className="row spacer">
              <button onClick={this.newRule}>Add Rule</button>
            </div>
          </div>
        </div>
      </>
    )
  }

  newRule(e) {
    e && e.preventDefault()

    this.setState(state => {
      var rule = cloneDeep(this.blankRule)
      rule.id = Math.random()
      state.pendingRules.push(rule)
      return state
    })
  }

  validRule(rule) {
    const fn = this.getFunction(rule.trigger.fn)
    return (
      (!fn.uses_field || (rule.trigger && rule.trigger.field)) &&
      (!fn.params ||
        fn.params.filter((p, i) => !rule.trigger.params[i]).length == 0)
    )
  }

  changeRule(path, id, val) {
    const formRules = this.props.form.routing_rules
    this.setState(state => {
      var rule = this.getRule(state.pendingRules, id)
      if (!rule) {
        rule = cloneDeep(this.getRule(formRules, id))
        this.state.pendingRules.push(rule)
      }

      if (
        this.idIsTemporary(id) ||
        val !== get(this.getRule(formRules, rule.id), path)
      ) {
        rule.dirty = true
      } else {
        rule.dirty = false
      }

      set(rule, path, val)

      return state
    })
  }

  getFunction(fn_name) {
    for (let i = 0; i < window.formspree.rule_fns.length; i++) {
      let fn = window.formspree.rule_fns[i]
      if (fn.name == fn_name) return fn
    }
  }

  listAllRules() {
    const pending = this.state.pendingRules
    const saved = this.props.form.routing_rules
    var all = []
    for (let i = 0; i < saved.length; i++) {
      let savedRule = saved[i]
      all.push(this.getRule(pending, savedRule.id) || savedRule)
    }
    for (let i = 0; i < pending.length; i++) {
      if (this.idIsTemporary(pending[i].id)) {
        all.push(pending[i])
      }
    }
    return all
  }

  idIsTemporary(id) {
    return typeof id === 'number'
  }

  getRule(rules, id) {
    for (let i = 0; i < rules.length; i++) {
      if (rules[i].id == id) {
        return rules[i]
      }
    }
    return null
  }

  async saveRule(e, id) {
    e.preventDefault()

    let rule = this.getRule(this.state.pendingRules, id)
    if (!rule) return

    await ajax({
      method: this.idIsTemporary(id) ? 'POST' : 'PUT',
      endpoint:
        `/api-int/forms/${this.props.form.hashid}/rules` +
        (this.idIsTemporary(id) ? '' : `/${rule.id}`),
      payload: {email: rule.email, trigger: rule.trigger},
      errorMsg: 'Failed to save rule',
      successMsg: 'Rule saved.',
      onSuccess: async r => {
        await this.props.reloadSpecificForm(this.props.form.hashid)
        this.props.ready()
        this.setState(state => {
          state.pendingRules = state.pendingRules.filter(el => el.id != id)
          return state
        })
      }
    })
  }

  async deleteRule(e, id) {
    e.preventDefault()

    let rule = this.getRule(this.listAllRules(), id)
    if (!rule) return

    if (this.idIsTemporary(id)) {
      this.setState(state => {
        state.pendingRules = state.pendingRules.filter(el => el.id != id)
      })
      return
    }

    await ajax({
      method: 'DELETE',
      endpoint: `/api-int/forms/${this.props.form.hashid}/rules/${rule.id}`,
      errorMsg: 'Failed to delete rule',
      successMsg: 'Rule deleted.',
      onSuccess: async r => {
        await this.props.reloadSpecificForm(this.props.form.hashid)
        this.props.ready()
      }
    })
  }
}

export default props => (
  <>
    <AccountContext.Consumer>
      {({emails, reloadSpecificForm}) => (
        <LoadingContext.Consumer>
          {({ready, wait}) => (
            <FormRoutingRules
              {...props}
              emails={emails}
              reloadSpecificForm={reloadSpecificForm}
              ready={ready}
            />
          )}
        </LoadingContext.Consumer>
      )}
    </AccountContext.Consumer>
  </>
)
