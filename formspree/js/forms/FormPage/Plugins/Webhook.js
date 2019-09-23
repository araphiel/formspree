/** @format */

import * as toast from '../../../toast'
const React = require('react')

import LoaderButton from '../../../components/LoaderButton'
import ActionInput from '../../../components/ActionInput'
import ajax from '../../../ajax'
import {PluginControls} from '.'

export default class Webhook extends React.Component {
  constructor(props) {
    super(props)
    this.handle = this.handle.bind(this)
  }

  render() {
    let {info, authed} = this.props.plugin

    if (!authed) {
      return (
        <form onSubmit={this.handle}>
          <div className="row">
            <p>
              Webhooks allow you to send submissions to a server endpoint that's
              tailored to accept our JSON payload.
            </p>
          </div>
          <div className="row spacer">
            <label>
              Target URL:{' '}
              <input
                name="target_url"
                placeholder="https://my-webhook-handler.com/"
                type="url"
              />
            </label>
          </div>
          <div className="row spacer right">
            <LoaderButton className="LoaderButton">Connect</LoaderButton>
          </div>
        </form>
      )
    }

    return (
      <div id="webhook-settings">
        <label>
          Target URL:
          <ActionInput value={info.target_url} copyButton />
        </label>
        <PluginControls {...this.props} />
      </div>
    )
  }

  async handle(e) {
    e.preventDefault()

    await ajax({
      method: 'POST',
      endpoint: `/api-int/forms/${this.props.form.hashid}/plugins/webhook`,
      payload: {target_url: e.target.target_url.value},
      errorMsg: 'Failed to create webhook',
      successMsg: 'Webhook created successfully.',
      onSuccess: async () => {
        this.props.wait()
        await this.props.reloadSpecificForm(this.props.form.hashid)
      }
    })

    this.props.ready()
  }
}
