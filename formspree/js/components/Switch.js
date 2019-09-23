/** @format */

const React = require('react') // eslint-disable-line no-unused-vars

export default class Switch extends React.Component {
  constructor(props) {
    super(props)

    this.handleChange = this.handleChange.bind(this)
  }

  render() {
    let {fieldName, description, checked, disabled} = this.props

    return (
      <>
        <div className="switch">
          <div className="switch-container">
            <label className="switch-body">
              <input
                type="checkbox"
                onChange={this.handleChange}
                checked={checked}
                name={fieldName}
                disabled={disabled}
              />
              <span className="switch-slider" />
            </label>
          </div>
          <div className="switch-label">{this.props.children}</div>
        </div>
        {description && (
          <div className="switch-description">
            <p>{description}</p>
          </div>
        )}
      </>
    )
  }

  handleChange(e) {
    this.props.onChange(e.currentTarget.checked, this.props.fieldName)
  }
}
