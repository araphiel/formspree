/** @format */
import ActionInput from '../../components/ActionInput'

const Formspree = window.formspree

const cs = require('class-set')
const qs = require('query-string')
const React = require('react')
const CodeMirror = require('react-codemirror2')
require('codemirror/mode/xml/xml')
require('codemirror/mode/css/css')

import ajax from '../../ajax'
import {LoadingContext, AccountContext} from '../../Dashboard'
import LoaderButton from '../../components/LoaderButton'
import Modal from '../../components/Modal'
import Switch from '../../components/Switch'

import TEMPLATE_DEFAULTS from './TemplateDefaults'

const MODAL_REVERT = 'revert'
const MODAL_PREVIEW = 'preview'
const MODAL_SYNTAX = 'syntax'
const MODAL_DELETE = 'delete'

class FormWhitelabel extends React.Component {
  constructor(props) {
    super(props)

    this.updateTemplate = this.updateTemplate.bind(this)
    this.saveTemplateBody = this.saveTemplateBody.bind(this)
    this.saveTemplateMeta = this.saveTemplateMeta.bind(this)
    this.changeStyle = this.changeStyle.bind(this)
    this.changeBody = this.changeBody.bind(this)
    this.showModal = this.showModal.bind(this)
    this.showPreview = this.showPreview.bind(this)
    this.closeModal = this.closeModal.bind(this)
    this.changeTab = this.changeTab.bind(this)
    this.revert = this.revert.bind(this)

    this.previewIframe = React.createRef()

    this.defaultValues = {...TEMPLATE_DEFAULTS}

    this.availableTabs = ['HTML', 'CSS']

    this.state = {
      changes: {},
      modal: null,
      activeTab: 'HTML'
    }
  }

  renderSyntaxModal() {
    return (
      <>
        <Modal
          title="Email Syntax"
          isOpen={this.state.modal === MODAL_SYNTAX}
          closing={this.closeModal}
        >
          <div>
            <div>
              <p>
                the email body can contain simple HTML that's valid in an email.
                No <span className="code">&lt;script&gt;</span> or{' '}
                <span className="code">&lt;style&gt;</span> tags can be{' '}
                included. For a list of recommended HTML tags see{' '}
                <a
                  href="https://explore.reallygoodemails.com/new-to-email-coding-heres-where-to-start-2494422f0bd4"
                  target="_blank"
                >
                  this guide to HTML in email
                </a>
                .
              </p>
              <p>
                The following special variables are recognized by{' '}
                {Formspree.SERVICE_NAME}, using the{' '}
                <a
                  href="https://mustache.github.io/mustache.5.html"
                  target="_blank"
                >
                  mustache
                </a>{' '}
                template language.
              </p>
              <pre>
                {`
{{ _time }}         The date and time of the submission.
{{ _host }}         The URL of the form (without "https://").
{{ <fieldname> }}   Any named input value in your form.
{{# _fields }}      Starts a list of all fields.
  {{ _name }}       Within _fields, the current field name…
  {{ _value }}      … and field value.
{{/ _fields }}      Closes the _fields block.
{{ _unsubscribe }}  The unsubscribe link.

                `.trim()}
              </pre>
              <p>
                To mitigate spam, the template MUST include the{' '}
                <span>
                  <code>{'{{_unsubscribe}}'}</code>
                </span>{' '}
                link
              </p>
              <div className="row spacer right">
                <button className="deemphasize" onClick={this.closeModal}>
                  OK
                </button>
              </div>
            </div>
          </div>
        </Modal>
      </>
    )
  }

  renderRevertModal() {
    return (
      <>
        <Modal
          title="Are you sure?"
          isOpen={this.state.modal === MODAL_REVERT}
          closing={this.closeModal}
          className="narrow"
        >
          <div className="left">
            <p>
              Reverting will discard the changes you've made to your email
              template.
            </p>
            <div className="row spacer">
              <button className="deemphasize" onClick={this.closeModal}>
                Cancel
              </button>
              <div className="right" style={{float: 'right'}}>
                <button className="emphasize" onClick={this.revert}>
                  Revert
                </button>
              </div>
            </div>
          </div>
        </Modal>
      </>
    )
  }

  renderPreviewModal() {
    return (
      <>
        <Modal
          title="Preview"
          isOpen={this.state.modal === MODAL_PREVIEW}
          closing={this.closeModal}
        >
          <div id="whitelabel-preview-modal">
            <iframe className="preview" ref={this.previewIframe} />
            <div className="row spacer right">
              <button className="deemphasize" onClick={this.closeModal}>
                OK
              </button>
            </div>
          </div>
        </Modal>
      </>
    )
  }

  renderDeleteModal() {
    return (
      <Modal
        title="Delete custom template?"
        isOpen={this.state.modal === MODAL_DELETE}
        closing={this.closeModal}
        className="narrow"
      >
        <p>
          Disabling your custom template will discard it, and use the{' '}
          {Formspree.SERVICE_NAME} template. Later, If you re-enable the custom
          template, you'll start with a default template.
        </p>
        <div className="row spacer">
          <button className="deemphasize" onClick={this.closeModal}>
            Cancel
          </button>
          <div className="right" style={{float: 'right'}}>
            <button
              onClick={this.saveTemplateBody}
              name={MODAL_DELETE}
              className="emphasize"
            >
              Delete
            </button>
          </div>
        </div>
      </Modal>
    )
  }

  render() {
    let {from_name, subject, style, body} = {
      ...this.defaultValues,
      ...this.props.form.template,
      ...this.state.changes
    }
    var shownCode
    switch (this.state.activeTab) {
      case 'CSS':
        shownCode = (
          <CodeMirror.Controlled
            value={style}
            options={{
              theme: 'oceanic-next',
              mode: 'css',
              viewportMargin: Infinity
            }}
            onBeforeChange={this.changeStyle}
          />
        )
        break
      case 'HTML':
        shownCode = (
          <CodeMirror.Controlled
            value={body}
            options={{
              theme: 'oceanic-next',
              mode: 'xml',
              viewportMargin: Infinity
            }}
            onBeforeChange={this.changeBody}
          />
        )
    }

    return (
      <>
        <div id="whitelabel">
          <div className="container">
            <div className="row">
              <ActionInput
                label="From"
                value={from_name}
                name="from_name"
                onChange={this.updateTemplate}
              >
                <LoaderButton
                  disabled={!this.state.changes.from_name}
                  onClick={this.saveTemplateMeta}
                  name="from_name"
                >
                  Save
                </LoaderButton>
              </ActionInput>
            </div>
            <div className="row spacer">
              <ActionInput
                label="Subject"
                value={subject}
                name="subject"
                description={
                  <>
                    Overrides <span className="code">_subject</span> field
                  </>
                }
                onChange={this.updateTemplate}
              >
                <LoaderButton
                  disabled={!this.state.changes.subject}
                  onClick={this.saveTemplateMeta}
                  name="subject"
                >
                  Save
                </LoaderButton>
              </ActionInput>
            </div>
            <div className="row spacer">
              {this.renderDeleteModal()}
              <Switch
                checked={
                  this.props.form.template &&
                  this.props.form.template.body !== undefined
                }
                onChange={this.saveTemplateBody}
              >
                <h4>Custom Email Template</h4>
              </Switch>
            </div>

            {this.props.form.template &&
              this.props.form.template.body && (
                <>
                  <div className="right">
                    <div className="syntax_ref">
                      <a href="#" onClick={this.showModal} name={MODAL_SYNTAX}>
                        syntax quick reference
                      </a>
                    </div>
                  </div>
                  {this.renderSyntaxModal()}
                  <div className="code-tabs">
                    {this.availableTabs.map(tabName => (
                      <div
                        key={tabName}
                        data-tab={tabName}
                        onClick={this.changeTab}
                        className={cs({
                          active: this.state.activeTab === tabName
                        })}
                      >
                        {tabName}
                      </div>
                    ))}
                  </div>
                  {shownCode}
                  <div className="row spacer">
                    {this.renderPreviewModal()}
                    <div className="col-1-3">
                      <button
                        onClick={() =>
                          this.showPreview(from_name, subject, style, body)
                        }
                      >
                        Preview
                      </button>
                    </div>
                    <div className="col-1-3 right">
                      {Object.keys(this.state.changes).length > 0
                        ? 'changes pending'
                        : '\u00A0'}
                    </div>
                    <div className="col-1-6 right">
                      {this.renderRevertModal()}
                      <button
                        name={MODAL_REVERT}
                        onClick={this.showModal}
                        disabled={Object.keys(this.state.changes).length === 0}
                      >
                        Revert
                      </button>
                    </div>
                    <div className="col-1-6 right">
                      <LoaderButton
                        onClick={this.saveTemplateBody}
                        disabled={Object.keys(this.state.changes).length === 0}
                      >
                        Deploy
                      </LoaderButton>
                    </div>
                  </div>
                </>
              )}
          </div>
        </div>
      </>
    )
  }

  updateTemplate(e) {
    let {name, value} = e.target
    this.setState(state => {
      state.changes[name] = value
      return state
    })
  }

  changeTab(e) {
    e.preventDefault()
    this.setState({activeTab: e.target.dataset.tab})
  }

  changeStyle(_, __, value) {
    this.setState(state => {
      state.changes.style = value
      return state
    })
  }

  changeBody(_, __, value) {
    this.setState(state => {
      state.changes.body = value
      return state
    })
  }

  showModal(eventOrValue) {
    const modal = eventOrValue.target ? eventOrValue.target.name : eventOrValue
    this.setState({modal})
  }

  showPreview(from_name, subject, style, body) {
    this.setState({modal: MODAL_PREVIEW})
    ajax({
      method: 'POST',
      endpoint: '/api-int/forms/whitelabel/preview',
      payload: {from_name, subject, style, body},
      json: false,
      onSuccess: html => {
        this.previewIframe.current.src =
          'data:text/html;charset=utf-8,' + encodeURI(html)
      }
    })
  }

  closeModal() {
    this.setState({modal: null})
  }

  revert() {
    this.setState({changes: {}, modal: null})
  }

  async saveTemplateMeta(e) {
    const {name} = e.target
    await ajax({
      method: 'PUT',
      endpoint: `/api-int/forms/${this.props.form.hashid}/whitelabel`,
      payload: {[name]: this.state.changes[name]},
      errorMsg: `Failed to save ${name}`,
      successMsg: `Successfully saved ${name.replace('_', ' ')}`,
      onSuccess: async () => {
        await this.props.reloadSpecificForm(this.props.form.hashid)
        this.setState(state => {
          delete state.changes[name]
          return state
        })
      }
    })
    this.props.ready()
  }

  async saveTemplateBody(value) {
    let payload
    if (value === false) {
      /* called when toggling off the custom template */
      return this.showModal(MODAL_DELETE)
    } else if (value === true) {
      /* called when toggling back on the custom template */
      payload = {
        body: this.defaultValues.body,
        style: this.defaultValues.style
      }
    } else if (value.target && value.target.name === MODAL_DELETE) {
      /* called when deleting the template (from the delete modal) */
      this.closeModal()
      payload = {body: null, style: null}
    } else {
      /* called by the deploy button */
      payload = this.state.changes
    }
    await ajax({
      method: 'PUT',
      endpoint: `/api-int/forms/${this.props.form.hashid}/whitelabel`,
      payload: payload,
      errorMsg: `Failed to update template`,
      successMsg: `Successfully updated template`,
      onSuccess: async () => {
        await this.props.reloadSpecificForm(this.props.form.hashid)
        this.setState({
          changes: {}
        })
      }
    })
    this.props.ready()
  }
}

export default props => (
  <>
    <AccountContext.Consumer>
      {({reloadSpecificForm}) => (
        <LoadingContext.Consumer>
          {({ready, wait}) => (
            <FormWhitelabel
              {...props}
              reloadSpecificForm={reloadSpecificForm}
              ready={ready}
            />
          )}
        </LoadingContext.Consumer>
      )}
    </AccountContext.Consumer>
  </>
)
