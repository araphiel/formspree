/** @format */

import * as toast from '../../../toast'
const React = require('react')
const PromiseWindow = require('promise-window')

import ajax from '../../../ajax'
import ActionInput from '../../../components/ActionInput'
import LoaderButton from '../../../components/LoaderButton'
import {PluginControls} from '.'

export default class Mailchimp extends React.Component {
  constructor(props) {
    super(props)

    this.handle = this.handle.bind(this)
    this.choose = this.choose.bind(this)
    this.loadLists = this.loadLists.bind(this)
    this.isChoosable = this.isChoosable.bind(this)

    this.state = {
      step: null,
      lists: [],
      selectedList: undefined
    }
  }

  componentDidMount() {
    this.loadLists()
  }

  async loadLists() {
    if (this.props.plugin.authed) {
      await ajax({
        method: 'GET',
        endpoint: `/api-int/forms/${this.props.form.hashid}/plugins/mailchimp`,
        onSuccess: async lists => {
          this.setState({lists})
        },
        errorMsg: 'Failed to fetch lists'
      })
    }
  }

  render() {
    let {authed, info} = this.props.plugin
    let list_id = this.state.selectedList || info.list_id || -1
    let lists = this.state.lists
    let listOptions = lists.map(({id, name}) => ({label: name, value: id}))
    listOptions.unshift({
      label: '-- Please choose a list --',
      value: -1,
      disabled: true
    })

    return (
      <div id="mailchimp-settings">
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
        ) : authed ? (
          <div>
            <div className="row">
              <p>
                Choose a Mailchimp list, we'll add the email addresses of form
                submitters to that. To create a new list, visit the{' '}
                <a href="https://admin.mailchimp.com/lists/" target="_blank">
                  the Mailchimp Lists
                </a>{' '}
                admin page.
              </p>
            </div>
            <form onSubmit={this.choose}>
              <label className="row spacer">
                List:{' '}
                <div className="select">
                  <ActionInput
                    value={list_id}
                    onChange={e =>
                      this.setState({selectedList: e.target.value})
                    }
                    options={listOptions}
                    required
                  >
                    <LoaderButton disabled={!this.isChoosable()}>
                      Choose
                    </LoaderButton>
                  </ActionInput>
                </div>
              </label>
            </form>
            <PluginControls cantEnableYet={!info.list_id} {...this.props} />
          </div>
        ) : (
          <>
            <div className="row">
              <p>
                <a target="_blank" href="https://mailchimp.com">
                  Mailchimp
                </a>{' '}
                is a newsletter service. By connecting to Mailchimp, visitors
                will be added to your Mailchimp List directly when they submit
                your form.
              </p>
              <p>
                To work correctly, your form must have a{' '}
                <span>
                  <code>name</code>
                </span>{' '}
                or{' '}
                <span>
                  <code>_replyto</code>
                </span>{' '}
                input field.
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

    if (!this.props.plugin.authed) {
      PromiseWindow.open(
        `/forms/${this.props.form.hashid}/plugins/mailchimp/auth`,
        {width: 600, height: 500}
      )
        .then(async data => {
          if (this.state.step === 'authorizing') {
            this.setState({step: 'postauth'})
          }

          await this.props.reloadSpecificForm(this.props.form.hashid)
          await this.loadLists()
          this.props.ready()
        })
        .catch(async err => {
          this.setState({step: null})
          switch (err) {
            case 'closed':
              this.props.ready()
              break
            case 'mailchimp-failure':
              toast.warning(
                'Mailchimp returned an error when we tried to connect.'
              )
              break
            default:
              toast.warning(err)
              this.props.ready()
              break
          }
        })
    }
  }

  isChoosable() {
    return (
      this.state.selectedList &&
      this.state.selectedList !== this.props.plugin.info.list_id
    )
  }

  async choose(e) {
    e.preventDefault()

    await ajax({
      endpoint: `/api-int/forms/${this.props.form.hashid}/plugins/mailchimp`,
      method: 'PUT',
      payload: {
        list_id: this.state.selectedList || this.props.plugin.info.list_id
      },
      successMsg: 'Mailchimp plugin setup successfully.',
      errorMsg: 'Failed to setup Mailchimp plugin',
      onSuccess: async () => {
        await this.props.reloadSpecificForm(this.props.form.hashid)
      }
    })

    this.props.ready()
  }
}
