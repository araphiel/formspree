/** @format */

import * as toast from '../toast'

const React = require('react')
const ClipboardJS = require('clipboard')

export default class ActionInput extends React.Component {
  componentDidMount() {
    this.clipboard = new ClipboardJS('.actionInput button.copy')
    this.clipboard.on('success', function(e) {
      toast.success('Copied to clipboard.')
    })
  }

  componentWillUnmount() {
    this.clipboard.destroy()
  }

  renderRow() {
    const {
      label,
      description,
      value,
      options,
      copyButton,
      goButton,
      children,
      readOnly,
      rowOnly,
      ...attrs
    } = this.props
    return (
      <tr className="actionInput-row">
        <td>
          {options ? (
            <select
              value={value}
              readOnly={copyButton || goButton || readOnly}
              {...attrs}
            >
              {options.map(opt => (
                <option
                  value={opt.value}
                  key={opt.value}
                  disabled={opt.disabled}
                >
                  {opt.label}
                </option>
              ))}
            </select>
          ) : (
            <input
              value={value}
              readOnly={copyButton || goButton || readOnly}
              {...attrs}
            />
          )}
        </td>
        <td className="buttons">
          {copyButton && (
            <button className="copy deemphasize" data-clipboard-text={value}>
              Copy
            </button>
          )}
          {children}
          {goButton && (
            <button
              onClick={e => {
                e.preventDefault
                window.open(value, '_blank')
              }}
            >
              Go
            </button>
          )}
        </td>
      </tr>
    )
  }

  renderLabel() {
    const {label} = this.props
    return (
      <>
        {label && (
          <div className="actionInput-label">
            <h4>{label}</h4>
          </div>
        )}
      </>
    )
  }

  renderDescription() {
    const {description} = this.props
    return (
      <>
        {description && (
          <div className="actionInput-description">
            <span>{description}</span>
          </div>
        )}
      </>
    )
  }

  render() {
    const {rowOnly, className = ''} = this.props

    return (
      <>
        {rowOnly ? (
          this.renderRow()
        ) : (
          <div className={`actionInput ${className}`}>
            {this.renderLabel()}
            <table>
              <tbody>{this.renderRow()}</tbody>
            </table>
            {this.renderDescription()}
          </div>
        )}
      </>
    )
  }
}
