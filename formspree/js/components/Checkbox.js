/** @format */
const React = require('react') // eslint-disable-line no-unused-vars
import uuid from 'uuid/v4'

export default class Checkbox extends React.Component {
  constructor(props) {
    super(props)
    this.handleChange = this.handleChange.bind(this)
    this.id =
      this.props.id ||
      (this.props.fieldName ? 'cb-' + this.props.fieldName : uuid())
  }

  render() {
    let {fieldName, checked, disabled, className} = this.props
    return (
      <div className="checkbox">
        <input
          type="checkbox"
          onChange={this.handleChange}
          checked={checked}
          name={fieldName}
          disabled={disabled}
          id={this.id}
          className={'checkbox-input ' + className}
        />
        <label htmlFor={this.id} className="checkbox-label" />
      </div>
    )
  }

  handleChange(e) {
    this.props.onChange(e.currentTarget.checked, this.props.fieldName)
  }
}
