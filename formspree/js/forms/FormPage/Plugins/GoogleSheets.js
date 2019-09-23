/** @format */

import * as toast from '../../../toast'

const React = require('react')
const PromiseWindow = require('promise-window')

import {PluginControls} from '.'
import ActionInput from '../../../components/ActionInput'

function formName(form) {
  return form.name || `Formspree submissions for ${form.hashid}`
}

export default class GoogleSheets extends React.Component {
  constructor(props) {
    super(props)
    this.handle = this.handle.bind(this)
    this.state = {
      step: null
    }
  }

  spreadsheetURL(id) {
    return `https://docs.google.com/spreadsheets/d/${id}/edit`
  }

  render() {
    let {authed, info} = this.props.plugin

    return (
      <div id="google-sheets-settings">
        {this.state.step === 'authorizing' ? (
          <>
            <div className="center" style={{paddingTop: '40px'}}>
              <img src="/static/img/loading.svg" id="loading" />
            </div>
            <div className="center">Connecting ...</div>
            <div className="right" style={{paddingTop: '40px'}}>
              <button
                onClick={() => {
                  this.props.close()
                }}
              >
                Cancel
              </button>
            </div>
          </>
        ) : authed && info.spreadsheet_id ? (
          <div>
            {this.state.step === 'postauth' && (
              <div className="row spacer" style={{marginBottom: '20px'}}>
                We've created your new google sheet!
              </div>
            )}
            <label>
              Sheet URL:
              <ActionInput
                value={this.spreadsheetURL(info.spreadsheet_id)}
                copyButton
                goButton
              />
            </label>
            {this.state.step === 'postauth' ? (
              <div className="row spacer">
                <button className="deemphasize" onClick={this.props.close}>
                  OK
                </button>
              </div>
            ) : (
              <PluginControls {...this.props} />
            )}
          </div>
        ) : (
          <>
            <div className="row">
              <p>
                We'll copy your submissions into a new spreadsheet named{' '}
                <span className="code">{formName(this.props.form)}</span>.
              </p>
              <p>
                Each time someone submits this form, a new row will be added to
                the spreadsheet.
              </p>
            </div>
            <div className="row spacer right">
              <button onClick={this.handle}>Connect</button>
            </div>
          </>
        )}
      </div>
    )
  }

  handle(e) {
    e.preventDefault()

    this.setState({step: 'authorizing'})

    PromiseWindow.open(
      `/forms/${this.props.form.hashid}/plugins/google-sheets/auth`,
      {width: 601, height: 800}
    )
      .then(async data => {
        if (this.state.step === 'authorizing') {
          this.setState({step: 'postauth'})
          toast.success(`Created spreadsheet!`)
          await this.props.reloadSpecificForm(this.props.form.hashid)
          this.props.ready()
        }
      })
      .catch(async err => {
        this.setState({step: null})
        switch (err) {
          case 'closed':
            this.props.ready()
            break
          default:
            toast.warning(err)
            this.props.ready()
            break
        }
      })
  }
}
