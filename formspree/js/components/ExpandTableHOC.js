/** @format */

import React, {Component} from 'react'
import set from 'lodash.set'
import get from 'lodash.get'

export default TableComponent =>
  class ExpandTable extends Component {
    constructor(props) {
      super(props)
      this.state = {
        expanded: {}
      }
      this.getTdProps = this.getTdProps.bind(this)
    }

    // after initial render if we get new
    // data, columns, page changes, etc.
    // we reset expanded state.
    componentWillReceiveProps() {
      this.setState({
        expanded: {}
      })
    }

    getTdProps(tableState, rowInfo = {}, column) {
      if (column.id === '_selector') return {}
      return {
        // only override onClick for column Td
        onClick: e => {
          let {nestingPath} = rowInfo
          this.setState(prevState => {
            const isExpanded = get(prevState.expanded, nestingPath)
            // since we do not support nested rows, a shallow clone is okay.
            const newExpanded = {...prevState.expanded}
            set(newExpanded, nestingPath, isExpanded ? false : {})
            return {
              ...prevState,
              expanded: newExpanded
            }
          })
        }
      }
    }

    render() {
      return (
        <TableComponent
          {...this.props}
          expanded={this.state.expanded}
          getTdProps={this.getTdProps}
        />
      )
    }
  }
