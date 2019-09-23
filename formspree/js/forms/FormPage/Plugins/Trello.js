/** @format */

import * as toast from '../../../toast'
const React = require('react')
const PromiseWindow = require('promise-window')

import ajax from '../../../ajax'
import LoaderButton from '../../../components/LoaderButton'
import {PluginControls} from '.'

export default class Trello extends React.Component {
  constructor(props) {
    super(props)

    this.handle = this.handle.bind(this)
    this.choose = this.choose.bind(this)
    this.loadOptions = this.loadOptions.bind(this)
    this.isChoosable = this.isChoosable.bind(this)

    this.state = {
      step: null,
      boards: [],
      selectedBoard: undefined,
      selectedList: undefined
    }
  }

  componentDidMount() {
    this.loadOptions()
  }

  async loadOptions() {
    if (this.props.plugin.authed) {
      await ajax({
        method: 'GET',
        endpoint: `/api-int/forms/${this.props.form.hashid}/plugins/trello`,
        onSuccess: async boards => {
          this.setState({boards})
        },
        errorMsg: 'Failed to fetch options'
      })
    }
  }

  render() {
    let {authed, info} = this.props.plugin
    let board_id = this.state.selectedBoard || info.board_id
    let list_id = this.state.selectedList || info.list_id
    let boards = this.state.boards
    var lists = []
    if (board_id) {
      for (let i = 0; i < boards.length; i++) {
        if (boards[i]['id'] === board_id) {
          lists = boards[i]['lists']
        }
      }
    }

    return (
      <div id="trello-settings">
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
                Choose a Trello board and a list, we'll create a card there
                every time the form is submitted.
              </p>
            </div>
            <form onSubmit={this.choose}>
              <label className="row spacer">
                Board:{' '}
                <div className="select">
                  <select
                    value={board_id}
                    onChange={e =>
                      this.setState({selectedBoard: e.target.value})
                    }
                    required
                  >
                    <>
                      <option />
                      {boards.map(({id, name}) => (
                        <option key={id} value={id}>
                          {name}
                        </option>
                      ))}
                    </>
                  </select>
                </div>
              </label>
              <label className="row spacer">
                List:{' '}
                <div className="select">
                  <select
                    value={list_id}
                    onChange={e =>
                      this.setState({selectedList: e.target.value})
                    }
                    required
                  >
                    <>
                      <option />
                      {lists.map(({id, name}) => (
                        <option key={id} value={id}>
                          {name}
                        </option>
                      ))}
                    </>
                  </select>
                </div>
              </label>
              <div className="row spacer right">
                <LoaderButton disabled={!this.isChoosable()}>
                  Choose
                </LoaderButton>
              </div>
            </form>
            <PluginControls
              cantEnableYet={!info.board_id || !info.list_id}
              {...this.props}
            />
          </div>
        ) : (
          <>
            <div className="row">
              <p>Trello: love it or leave it.</p>
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
        `/forms/${this.props.form.hashid}/plugins/trello/auth`,
        {width: 601, height: 800}
      )
        .then(async data => {
          let token = data.hash.split('=')[1]

          await ajax({
            endpoint: `/api-int/forms/${this.props.form.hashid}/plugins/trello`,
            method: 'POST',
            payload: {token},
            onSuccess: async () => {
              if (this.state.step === 'authorizing') {
                this.setState({step: 'postauth'})
              }

              await this.props.reloadSpecificForm(this.props.form.hashid)
              await this.loadOptions()
              this.props.ready()
            },
            onError: async r => {
              throw r
            }
          })
        })
        .catch(async err => {
          this.setState({step: null})
          switch (err) {
            case 'closed':
              this.props.ready()
              break
            case 'trello-failure':
              toast.warning(
                'Trello returned an error when we tried to connect.'
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
      this.state.selectedBoard &&
      this.state.selectedBoard !== this.props.plugin.info.board_id &&
      this.state.selectedList &&
      this.state.selectedList !== this.props.plugin.info.list_id
    )
  }

  async choose(e) {
    e.preventDefault()

    await ajax({
      endpoint: `/api-int/forms/${this.props.form.hashid}/plugins/trello`,
      method: 'PUT',
      payload: {
        board_id: this.state.selectedBoard || this.props.plugin.info.board_id,
        list_id: this.state.selectedList || this.props.plugin.info.list_id
      },
      successMsg: 'Trello plugin setup successfully.',
      errorMsg: 'Failed to setup Trello plugin',
      onSuccess: async () => {
        await this.props.reloadSpecificForm(this.props.form.hashid)
      }
    })

    this.props.ready()
  }
}
