/** @format */

import LoaderButton from '../../components/LoaderButton'

/** @format */

const olark = window.olark

const React = require('react')
const prettyaml = require('prettyaml')
const moment = require('moment')
const shallowequals = require('shallow-equals')

import ReactTable from 'react-table'

import ajax from '../../ajax'
import {AccountContext, LoadingContext} from '../../Dashboard'
import Checkbox from '../../components/Checkbox'
import expandTableHOC from '../../components/ExpandTableHOC'

const SubmissionsTable = expandTableHOC(ReactTable)

class FormSubmissions extends React.Component {
  constructor(props) {
    super(props)

    this.selectRow = this.selectRow.bind(this)
    this.clearRows = this.clearRows.bind(this)
    this.deleteSubmissions = this.deleteSubmissions.bind(this)
    this.flagSubmissions = this.flagSubmissions.bind(this)
    this.showExportButtons = this.showExportButtons.bind(this)

    this.state = {
      exporting: false,
      animating: false,
      selected: [],
      filter: {spam: false}
    }
  }

  componentDidMount() {
    this.props.loadFormSubmissions(this.props.form.hashid, this.state.filter)
  }

  componentWillUnmount() {
    window.removeEventListener('scroll', this.scrollListener)
    window.removeEventListener('resize', this.resizeListener)
  }

  renderActions() {
    const {selected} = this.state
    return (
      <div
        id="submissionActions"
        className={!this.state.animating && selected.length ? 'active' : ''}
      >
        <div className="inner-frame right">
          <span className="sub-count">
            {selected.length} submission
            {selected.length > 1 && 's'}
          </span>
          <button className="deemphasize" onClick={this.clearRows}>
            cancel
          </button>
          <LoaderButton onClick={this.flagSubmissions}>
            {shallowequals(this.state.filter, {spam: false})
              ? 'spam'
              : 'not spam'}
          </LoaderButton>
          <LoaderButton onClick={this.deleteSubmissions} className="emphasize">
            delete
          </LoaderButton>
        </div>
      </div>
    )
  }

  renderFilter(filter, label) {
    return (
      <a
        className={
          'filter ' + (shallowequals(this.state.filter, filter) ? 'active' : '')
        }
        onClick={() => {
          this.props
            .loadFormSubmissions(this.props.form.hashid, filter)
            .then(() => {
              this.clearRows()
              this.setState({filter})
            })
        }}
      >
        {label}
      </a>
    )
  }

  render() {
    const {selected} = this.state
    const {form} = this.props

    if (!form.submissions) {
      return null
    }

    const parseDate = d => {
      let day = new Date(Date.parse(d))
      let now = Date.now()
      let format =
        day.month === now.month ? 'MMM DD, HH:mm' : 'MMM DD YYYY, HH:mm'
      return moment(day).format(format)
    }

    const parseValue = v => {
      var value
      try {
        value = prettyaml.stringify(v)
      } catch (e) {
        value = JSON.stringify(v)
      }
      return value
    }

    const accessor = field => row => {
      return field === '_date' ? parseDate(row[field]) : parseValue(row[field])
    }

    const renderExpandedRow = data => {
      return (
        <div className="submission-detail">
          {form.fields
            .filter(key => key !== '_id' && data.row[key])
            .map(key => {
              return (
                <div className="submission-field" key={key}>
                  <h4>{key}</h4>
                  <pre>{data.row[key]}</pre>
                </div>
              )
            })}
        </div>
      )
    }

    let columns = form.fields.map((f, i) => ({
      id: f,
      Header: f,
      accessor: accessor(f),
      show: i < 5 && (f !== '_id' && f !== '_errors')
    }))

    columns.push({
      id: '_selector',
      accessor: () => 'x', // this value is not important
      Header: null,
      Cell: rowInfo => (
        <Checkbox
          checked={selected.includes(rowInfo.row['_id'])}
          onChange={this.selectRow(rowInfo.row['_id'])}
          id={'cb-' + rowInfo.row['_id']}
          className="rowSelect"
        />
      ),
      width: 30,
      filterable: false,
      sortable: false,
      resizable: false,
      style: {textAlign: 'center'}
    })

    return (
      <div id="submissions">
        <div className="container">
          <div className="row">
            <div className="col-1-2">
              {this.renderFilter({spam: false}, 'inbox')} |{' '}
              {this.renderFilter({spam: true}, 'spam')}
            </div>
          </div>

          <SubmissionsTable
            selectType="checkbox"
            columns={columns}
            SubComponent={renderExpandedRow}
            data={form.submissions}
            defaultPageSize={10}
          />
          {form.submissions.length > 0 && (
            <>
              <div className="row spacer">
                {this.state.exporting &&
                !shallowequals(this.state.filter, {spam: true}) ? (
                  <div className="col-1-1 right">
                    <a
                      target="_blank"
                      className="button"
                      style={{marginRight: '5px'}}
                      href={`/forms/${form.hashid}.json`}
                    >
                      Export as JSON
                    </a>
                    <a
                      target="_blank"
                      className="button"
                      href={`/forms/${form.hashid}.csv`}
                    >
                      Export as CSV
                    </a>
                  </div>
                ) : (
                  <div className="col-1-1 right">
                    <button onClick={this.showExportButtons}>Export</button>
                  </div>
                )}
              </div>
              {this.renderActions()}
            </>
          )}
        </div>
      </div>
    )
  }

  showExportButtons(e) {
    e.preventDefault()
    this.setState({exporting: true})
  }

  selectRow(id) {
    return e => {
      let selected = this.state.selected.slice()
      if (selected.includes(id)) {
        selected = selected.filter(x => x !== id)
      } else {
        selected.push(id)
      }
      let wasVisible = this.state.selected.length > 0
      let isVisible = selected.length > 0
      let changedVisibility = wasVisible !== isVisible

      if (changedVisibility) {
        isVisible ? olark('api.box.hide') : olark('api.box.show')
      }

      this.setState(prev => ({...prev, selected}))
    }
  }

  clearRows() {
    olark('api.box.show')
    this.setState({selected: []})
  }

  async deleteSubmissions() {
    let hashid = this.props.form.hashid
    await ajax({
      method: 'DELETE',
      endpoint: `/api-int/forms/${hashid}/submissions`,
      payload: {submissions: this.state.selected},
      onSuccess: result => {
        this.props.loadFormSubmissions(hashid, this.state.filter)
        this.props.form.counter = result.counter
        this.props.updateFormState(hashid, this.props.form)
        this.setState({selected: []})
        this.props.ready()
      },
      successMsg: 'Submissions deleted.',
      errorMsg: 'Failed to delete submissions'
    })
  }

  async flagSubmissions() {
    let hashid = this.props.form.hashid
    await ajax({
      method: 'PATCH',
      endpoint: `/api-int/forms/${hashid}/submissions`,
      payload: {
        submissions: this.state.selected,
        operation: {spam: !shallowequals(this.state.filter, {spam: true})}
      },
      onSuccess: result => {
        this.props.loadFormSubmissions(hashid, this.state.filter)
        this.props.form.counter = result.counter
        this.props.updateFormState(hashid, this.props.form)
        this.setState({selected: []})
        this.props.ready()
      },
      successMsg: 'Submissions updated.',
      errorMsg: 'Failed to update submissions'
    })
  }
}

export default props => (
  <>
    <AccountContext.Consumer>
      {({loadFormSubmissions, updateFormState}) => (
        <LoadingContext.Consumer>
          {({ready, wait}) => (
            <FormSubmissions
              {...props}
              ready={ready}
              wait={wait}
              loadFormSubmissions={loadFormSubmissions}
              updateFormState={updateFormState}
            />
          )}
        </LoadingContext.Consumer>
      )}
    </AccountContext.Consumer>
  </>
)
