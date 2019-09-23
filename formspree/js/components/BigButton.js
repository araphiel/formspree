/** @format */

const React = require('react')
const cs = require('class-set')

export default class BigButton extends React.Component {
  render() {
    const {iconClass, active, enabled, onClick} = this.props
    return (
      <button
        style={{width: '100%'}}
        className={cs({
          bigButton: true,
          deemphasize: !active,
          disabled: active && !enabled
        })}
        onClick={onClick}
      >
        <div className="v-middle">
          <span className={iconClass + ' bigButton-icon'} />
          <span
            className="bigButton-label"
            style={{marginLeft: iconClass && '1em'}}
          >
            {this.props.children}
          </span>
        </div>
      </button>
    )
  }
}
