/** @format */

const formspree = window.formspree
const React = require('react')

import memoize from 'memoize-one'

import {AccountContext, LoadingContext} from '../../../Dashboard'
import BigButton from '../../../components/BigButton'
import Modal from '../../../components/Modal'
import Switch from '../../../components/Switch'
import DeleteSwitch from '../../../components/DeleteSwitch'
import ajax from '../../../ajax'

import GoogleSheets from './GoogleSheets'
import Webhook from './Webhook'
import Trello from './Trello'
import Slack from './Slack'
import Mailchimp from './Mailchimp'

const MODAL_GOOGLE_SHEETS = 'MODAL_GOOGLE_SHEETS'
const MODAL_WEBHOOK = 'MODAL_WEBHOOK'
const MODAL_TRELLO = 'MODAL_TRELLO'
const MODAL_SLACK = 'MODAL_SLACK'
const MODAL_MAILCHIMP = 'MODAL_MAILCHIMP'

class FormPlugins extends React.Component {
  constructor(props) {
    super(props)

    this.closeModal = this.closeModal.bind(this)

    this.emptyPlugin = {
      authed: false,
      enabled: false,
      info: {}
    }

    this.getPluginsList = memoize(form => {
      var plugins = {}

      for (let i = 0; i < form.plugins.length; i++) {
        let plugin = form.plugins[i]
        plugins[plugin.kind] = plugin
      }
      for (let i = 0; i < formspree.plugins.length; i++) {
        let kind = formspree.plugins[i]
        if (!plugins[kind]) {
          plugins[kind] = {kind, ...this.emptyPlugin}
        }
      }

      return plugins
    })

    this.state = {
      modal: null
    }
  }

  render() {
    let plugins = this.getPluginsList(this.props.form)

    return (
      <>
        <div id="plugins" className="container">
          <div className="row">
            <Modal
              title={
                plugins['google-sheets'].authed
                  ? 'Google Sheets Settings'
                  : 'Connect to Google Sheets'
              }
              isOpen={this.state.modal === MODAL_GOOGLE_SHEETS}
              closing={this.closeModal}
              className="narrow"
            >
              <GoogleSheets
                plugin={plugins['google-sheets']}
                close={this.closeModal}
                {...this.props}
              />
            </Modal>

            <div className="col-1-3">
              <BigButton
                active={plugins['google-sheets'].authed}
                enabled={plugins['google-sheets'].enabled}
                onClick={this.openModal(MODAL_GOOGLE_SHEETS)}
                iconClass="icon-google"
              >
                Google Sheets
              </BigButton>
            </div>

            <Modal
              title={
                plugins['mailchimp'].authed
                  ? 'Mailchimp Settings'
                  : 'Connect to Mailchimp'
              }
              isOpen={this.state.modal === MODAL_MAILCHIMP}
              closing={this.closeModal}
              className="narrow"
            >
              <Mailchimp
                plugin={plugins['mailchimp']}
                close={this.closeModal}
                {...this.props}
              />
            </Modal>

            <div className="col-1-3">
              <BigButton
                active={plugins['mailchimp'].authed}
                enabled={plugins['mailchimp'].enabled}
                onClick={this.openModal(MODAL_MAILCHIMP)}
                iconClass="icon-mailchimp"
              >
                Mailchimp
              </BigButton>
            </div>

            <Modal
              title={
                plugins['webhook'].authed
                  ? 'Webhook Settings'
                  : 'Connect a Webhook'
              }
              isOpen={this.state.modal === MODAL_WEBHOOK}
              closing={this.closeModal}
              className="narrow"
            >
              <Webhook
                plugin={plugins['webhook']}
                close={this.closeModal}
                {...this.props}
              />
            </Modal>

            <div className="col-1-3">
              <BigButton
                active={plugins['webhook'].authed}
                enabled={plugins['webhook'].enabled}
                onClick={this.openModal(MODAL_WEBHOOK)}
              >
                Webhook
              </BigButton>
            </div>
          </div>

          {/*
          <div className="row spacer">

            <Modal
              title={
                plugins['trello'].authed
                  ? 'Trello Settings'
                  : 'Connect to a Trello list'
              }
              isOpen={this.state.modal === MODAL_TRELLO}
              closing={this.closeModal}
              className="narrow"
            >
              <Trello
                plugin={plugins['trello']}
                close={this.closeModal}
                {...this.props}
              />
            </Modal>

            <div className="col-1-3">
              <BigButton
                active={plugins['trello'].authed}
                enabled={plugins['trello'].enabled}
                onClick={this.openModal(MODAL_TRELLO)}
                iconClass="icon-trello"
              >
                Trello
              </BigButton>
            </div>

            <Modal
              title={
                plugins['slack'].authed
                  ? 'Slack Settings'
                  : 'Connect to a Slack channel'
              }
              isOpen={this.state.modal === MODAL_SLACK}
              closing={this.closeModal}
              className="narrow"
            >
              <Slack
                plugin={plugins['slack']}
                close={this.closeModal}
                {...this.props}
              />
            </Modal>

            <div className="col-1-3">
              <BigButton
                active={plugins['slack'].authed}
                enabled={plugins['slack'].enabled}
                onClick={this.openModal(MODAL_SLACK)}
                iconClass="icon-slack"
              >
                Slack
              </BigButton>
            </div>

            <div className="col-1-3" />
          </div>
          */}
        </div>
      </>
    )
  }

  openModal(what) {
    return e => {
      e.preventDefault()

      this.setState({modal: what})
    }
  }

  closeModal() {
    this.setState({modal: null})
  }
}

export class PluginControls extends React.Component {
  constructor(props) {
    super(props)

    this.toggleEnabled = this.toggleEnabled.bind(this)
    this.delete = this.delete.bind(this)

    this.state = {
      tmp: null
    }
  }

  render() {
    return (
      <>
        <div className="row spacer">
          <div className="col-1-1">
            <Switch
              checked={
                this.state.tmp === null
                  ? this.props.plugin.enabled
                  : this.state.tmp
              }
              disabled={this.props.cantEnableYet}
              onChange={this.toggleEnabled}
            >
              Enabled
            </Switch>
          </div>
        </div>
        <div className="row spacer">
          <div className="col-1-1">
            <DeleteSwitch
              narrow
              label="Disconnect"
              warningTitle="Are you sure you want to disconnect?"
              onDelete={this.delete}
            >
              Disconnect Plugin
            </DeleteSwitch>
          </div>
        </div>
      </>
    )
  }

  async toggleEnabled(enabled) {
    let {kind} = this.props.plugin
    this.setState({tmp: enabled}, async () => {
      await ajax({
        method: 'PATCH',
        endpoint: `/api-int/forms/${this.props.form.hashid}/plugins/${kind}`,
        payload: {enabled: enabled},
        errorMsg: `Failed to ${enabled ? 'enable' : 'disable'} plugin`,
        successMsg: `Plugin ${enabled ? 'enabled' : 'disabled'}.`,
        onSuccess: async () => {
          await this.props.reloadSpecificForm(this.props.form.hashid)
        }
      })

      this.setState({tmp: null})
    })
  }

  async delete() {
    await ajax({
      method: 'DELETE',
      endpoint: `/api-int/forms/${this.props.form.hashid}/plugins/${
        this.props.plugin.kind
      }`,
      errorMsg: 'Failed to disconnect plugin',
      successMsg: 'Plugin disconnected.',
      onSuccess: async () => {
        this.props.wait()
        return this.props.reloadSpecificForm(this.props.form.hashid)
      }
    })

    this.props.ready()
  }
}

export default props => (
  <AccountContext.Consumer>
    {({reloadSpecificForm}) => (
      <LoadingContext.Consumer>
        {({ready, wait}) => (
          <FormPlugins
            {...props}
            reloadSpecificForm={reloadSpecificForm}
            wait={wait}
            ready={ready}
          />
        )}
      </LoadingContext.Consumer>
    )}
  </AccountContext.Consumer>
)
