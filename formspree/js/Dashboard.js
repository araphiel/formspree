/** @format */

const olark = window.olark
const amplitude = window.amplitude
const url = require('url')

const React = require('react')
const {StripeProvider} = require('react-stripe-elements')
const {
  BrowserRouter,
  Route,
  Redirect,
  Switch,
  Link
} = require('react-router-dom')

import ajax from './ajax'
import Portal from './Portal'
import FormList from './forms/FormList'
import FormPage from './forms/FormPage'
import Account from './users/Account'
import Billing from './users/Billing'
import Plans from './users/Plans'
import {PageTransition, logPageTransition} from './PageTransition'

export const AccountContext = React.createContext()
export const LoadingContext = React.createContext()

export default class Dashboard extends React.Component {
  constructor() {
    super()

    this.loadAccountData = this.loadAccountData.bind(this)
    this.loadFormsList = this.loadFormsList.bind(this)
    this.loadSpecificForm = this.loadSpecificForm.bind(this)
    this.loadFormSubmissions = this.loadFormSubmissions.bind(this)
    this.updateFormState = this.updateFormState.bind(this)
    this.wait = this.wait.bind(this)
    this.waitButton = this.waitButton.bind(this)
    this.bootDashboard = this.bootDashboard.bind(this)
    this.ready = this.ready.bind(this)

    this.state = {
      account: {},
      forms: [],

      waitingPage: true,
      waitingButton: null
    }
  }

  componentDidMount() {
    Promise.all([
      this.loadAccountData(
        location.pathname === '/plans' ? {errorMsg: null} : {}
      ),
      this.loadFormsList(location.pathname === '/plans' ? {errorMsg: null} : {})
    ]).then(() => {
      this.bootDashboard()
      this.ready()
    })
  }

  render() {
    if (this.state.waitingPage) {
      return (
        <div className=" center">
          <img src="/static/img/loading.svg" id="loading" />
        </div>
      )
    }

    return (
      <BrowserRouter>
        <PageTransition>
          <StripeProvider apiKey={window.formspree.STRIPE_PUBLISHABLE_KEY}>
            <AccountContext.Provider
              value={{
                ...this.state.account,
                forms: this.state.forms,

                reloadAccount: this.loadAccountData,
                reloadFormsList: this.loadFormsList,
                reloadSpecificForm: this.loadSpecificForm,
                loadFormSubmissions: this.loadFormSubmissions,
                updateFormState: this.updateFormState
              }}
            >
              <LoadingContext.Provider
                value={{
                  waitingPage: this.state.waitingPage,
                  waitingButton: this.state.waitingButton,

                  wait: this.wait,
                  waitButton: this.waitButton,
                  ready: this.ready
                }}
              >
                <Portal to="#forms-menu-item">
                  <Link to="/forms">Forms</Link>
                </Portal>
                <Portal to="#account-menu-item">
                  <Link to="/account">Account</Link>
                </Portal>
                <Switch>
                  <Redirect from="/dashboard" to="/forms" />
                  <Route exact path="/plans" component={Plans} />
                  <Route exact path="/account" component={Account} />
                  <Route exact path="/account/billing" component={Billing} />
                  <Route exact path="/forms" component={FormList} />
                  <Route path="/forms/:hashid" component={FormPage} />
                </Switch>
              </LoadingContext.Provider>
            </AccountContext.Provider>
          </StripeProvider>
        </PageTransition>
      </BrowserRouter>
    )
  }

  async loadAccountData(opts = {}) {
    return ajax({
      method: 'GET',
      endpoint: '/api-int/account',
      errorMsg: 'Failed to fetch your account data',
      onSuccess: r => {
        this.setState({
          account: {
            user: r.user,
            emails: r.emails,
            sub: r.sub,
            cards: r.cards,
            invoices: r.invoices
          }
        })

        olark('api.chat.onBeginConversation', function() {
          ;[
            `user is on plan ${r.user.plan}.`,
            `registered since ${r.user.registered_on}.`,
            `verified emails: [${r.emails.verified.join(' ')}].`,
            `pending emails: [${r.emails.pending.join(' ')}].`
          ].map(msg => {
            olark('api.chat.sendNotificationToOperator', {body: msg})
          })
        })

        olark('api.chat.updateVisitorStatus', {
          snippet: [`plan: ${r.user.plan}`]
        })
      },
      ...opts
    })
  }

  async loadFormsList(opts = {}) {
    await ajax({
      method: 'GET',
      endpoint: '/api-int/forms',
      onSuccess: r => {
        this.setState({
          forms: r.forms
        })

        olark('api.chat.onBeginConversation', function() {
          olark('api.chat.sendNotificationToOperator', {
            body: `user has access to ${r.forms.length} forms.`
          })
        })
      },
      errorMsg: 'Error fetching forms list',
      ...opts
    })
  }

  async loadSpecificForm(hashid) {
    await ajax({
      method: 'GET',
      endpoint: `/api-int/forms/${hashid}`,
      onSuccess: form => {
        this.setState(state => {
          for (let i = 0; i < state.forms.length; i++) {
            if (state.forms[i].hashid === form.hashid) {
              state.forms[i] = form
              return state
            }
          }

          // if form wasn't in the list (is new), add it to the top
          state.forms.unshift(form)
          return state
        })
      },
      errorMsg: `Error loading form '${hashid}'`
    })
  }

  async loadFormSubmissions(hashid, filter = {}) {
    await ajax({
      method: 'GET',
      endpoint: `/api-int/forms/${hashid}/submissions`,
      params: {filter},
      onSuccess: ({submissions, fields}) => {
        this.setState(state => {
          for (let i = 0; i < state.forms.length; i++) {
            let form = state.forms[i]
            if (form.hashid === hashid) {
              form.submissions = submissions
              form.fields = fields
              break
            }
          }
          return state
        })
      },
      errorMsg: 'Error fetching submissions'
    })
  }

  updateFormState(hashid, form) {
    this.setState(state => {
      for (let i = 0; i < state.forms.length; i++) {
        if (state.forms[i].hashid === hashid) {
          state.forms[i] = form
          break
        }
      }
      return state
    })
  }

  wait() {
    this.setState({waitingPage: true})
  }

  waitButton(buttonId) {
    this.setState({waitingButton: buttonId})
  }

  bootDashboard() {
    const {user} = this.state.account
    const ampInst = amplitude && amplitude.getInstance()
    if (ampInst) {
      ampInst.init(window.formspree.AMPLITUDE_KEY, user ? user.id : null, {
        // Configuration options. Do not change without consulting legal.
        includeReferrer: true,
        includeUtm: true,
        saveParamsReferrerOncePerSession: false,
        trackingOptions: {
          carrier: true,
          city: false,
          country: true,
          device_model: true,
          dma: false,
          ip_address: false,
          language: true,
          os_name: true,
          os_version: true,
          platform: true,
          region: false,
          version_name: true
        }
      })
      if (user) {
        const identify = new amplitude.Identify().set('e', user.email)
        ampInst.identify(identify)
        olark('api.visitor.updateEmailAddress', {
          emailAddress: user.email
        })
      }

      logPageTransition(url.parse(window.location.href).pathname)
    }
  }

  ready() {
    this.setState({waitingButton: null, waitingPage: false})
  }
}
