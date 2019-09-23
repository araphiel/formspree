/** @format */

import * as toast from '../../../toast'
const React = require('react')
const PromiseWindow = require('promise-window')

import {PluginControls} from '.'

export default class Slack extends React.Component {
  constructor(props) {
    super(props)
    this.handle = this.handle.bind(this)
    this.state = {
      step: null
    }
  }

  render() {
    let {authed, info} = this.props.plugin

    return (
      <div id="slack-settings">
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
        ) : authed && info.incoming_webhook ? (
          <div>
            {this.state.step === 'postauth' && (
              <div className="row spacer" style={{marginBottom: '20px'}}>
                We've connected to your team {info.team_name}!
              </div>
            )}
            <label>
              <p>
                Posting submissions to <b>{info.incoming_webhook.channel}</b> on{' '}
                <a
                  href={info.incoming_webhook.configuration_url}
                  target="_blank"
                >
                  {info.team_name}
                </a>
                .
              </p>
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
              <p>Post stuff to a Slack channel of your choice.</p>
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

    PromiseWindow.open(`/forms/${this.props.form.hashid}/plugins/slack/auth`, {
      width: 601,
      height: 800
    })
      .then(async data => {
        if (this.state.step === 'authorizing') {
          this.setState({step: 'postauth'})
          toast.success(`Connected to ${data.channel} on team ${data.team}!`)
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
          case 'access-denied':
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
